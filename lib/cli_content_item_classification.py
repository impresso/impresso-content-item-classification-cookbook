#!/usr/bin/env python3
"""
CLI tool for content item ad classification with smart_open and logging.

This script follows the cookbook CLI conventions:
- required `--input` and `--output` arguments
- smart_open-based local/S3 I/O via get_transport_params()
- setup_logging() for consistent logging output

Input is expected to be JSONL or JSONL.BZ2. Output is minimal JSONL where every
row contains `id` and `tp`, and rows classified as articles additionally contain
the configured ad classification field.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, TextIO, Tuple

from smart_open import open as smart_open  # type: ignore

from impresso_cookbook import get_transport_params, setup_logging  # type: ignore

log = logging.getLogger(__name__)

DEFAULT_AD_VALUE = "ad"
DEFAULT_NON_AD_VALUE = "non-ad"


@dataclass(frozen=True)
class ClassifierConfig:
    """Runtime config for the ad classifier pipeline."""

    diagnostics: bool
    precision: Optional[int]
    batch_size: int


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Command-line arguments (uses sys.argv if None)

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description=(
            "Classify ad/non-ad content items from local or S3 JSONL(.bz2) input "
            "and write minimal JSONL output."
        )
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        help="Write log to FILE",
        metavar="FILE",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument(
        "-i",
        "--input",
        "--input-path",
        dest="input",
        help="Input JSONL/JSONL.BZ2 file (required)",
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output",
        "--output-path",
        dest="output",
        help="Output JSONL/JSONL.BZ2 file (required)",
        required=True,
    )
    parser.add_argument(
        "--id-field",
        default="id",
        help="Input ID field name (default: %(default)s)",
    )
    parser.add_argument(
        "--text-field",
        default="ft",
        help="Input text field used by classifier (default: %(default)s)",
    )
    parser.add_argument(
        "--type-field",
        default="tp",
        help="Input type field used to select rows for classification (default: %(default)s)",
    )
    parser.add_argument(
        "--type-value",
        default="ar",
        help="Only rows with this type value are classified (default: %(default)s)",
    )
    parser.add_argument(
        "--class-field",
        default="ad_classification",
        help="Output field name for ad/non-ad decision (default: %(default)s)",
    )
    parser.add_argument(
        "--classifier-batch-size",
        type=int,
        default=64,
        help="Batch size for classifier inference (default: %(default)s)",
    )
    parser.add_argument(
        "--pipeline-diagnostics",
        action="store_true",
        help="Enable diagnostics mode when constructing AdClassifierPipeline",
    )
    parser.add_argument(
        "--pipeline-precision",
        type=int,
        default=2,
        help="Precision forwarded to pipeline(..., precision=...) (default: %(default)s)",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Log progress every N classified records (default: %(default)s)",
    )

    options = parser.parse_args(args)

    _validate_jsonl_path(parser, options.input, "--input")
    _validate_jsonl_path(parser, options.output, "--output")

    if options.classifier_batch_size <= 0:
        parser.error("--classifier-batch-size must be > 0")
    if options.progress_every <= 0:
        parser.error("--progress-every must be > 0")

    return options


def _validate_jsonl_path(
    parser: argparse.ArgumentParser,
    path: str,
    argument_name: str,
) -> None:
    """Validate supported JSONL path suffixes."""
    lowered = path.lower()
    if lowered.endswith(".jsonl") or lowered.endswith(".jsonl.bz2"):
        return
    parser.error(f"{argument_name} must end with .jsonl or .jsonl.bz2")


def ensure_local_parent(path: str) -> None:
    """Create the parent directory for local output paths when needed."""
    if path.startswith("s3://"):
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def as_str(value: Any) -> str:
    """Convert a value to a stripped string."""
    if value is None:
        return ""
    return str(value).strip()


def _extract_type_label_from_output(output: Any) -> Optional[str]:
    """Extract the classifier label from supported pipeline outputs."""
    if isinstance(output, list):
        if not output:
            return None
        return _extract_type_label_from_output(output[0])

    if isinstance(output, dict) and "type" in output:
        label = as_str(output.get("type"))
        if label:
            return label

    return None


def _pipeline_predict_batch(
    pipeline: Any,
    texts: Sequence[str],
    precision: Optional[int],
) -> List[Any]:
    """Run the pipeline in batch mode with compatibility fallbacks."""

    def _call(payload: Any) -> Any:
        if precision is None:
            return pipeline(payload)
        try:
            return pipeline(payload, precision=precision)
        except TypeError:
            return pipeline(payload)

    result = _call(list(texts))
    if isinstance(result, list) and len(result) == len(texts):
        return result
    if len(texts) == 1:
        return result if isinstance(result, list) else [result]

    outputs: List[Any] = []
    for text in texts:
        single = _call(text)
        if isinstance(single, list):
            outputs.append(single[0] if single else {})
        else:
            outputs.append(single)
    return outputs


class ContentItemClassificationProcessor:
    """Process JSONL input and classify article rows as ad/non-ad."""

    def __init__(
        self,
        input_file: str,
        output_file: str,
        id_field: str = "id",
        text_field: str = "ft",
        type_field: str = "tp",
        type_value: str = "ar",
        class_field: str = "ad_classification",
        classifier_batch_size: int = 64,
        pipeline_diagnostics: bool = False,
        pipeline_precision: Optional[int] = 2,
        progress_every: int = 500,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
    ) -> None:
        """
        Initialize the content item classification processor.

        Args:
            input_file: Path to the input JSONL/JSONL.BZ2 file
            output_file: Path to the output JSONL/JSONL.BZ2 file
            id_field: Input record ID field name
            text_field: Input text field name used for classification
            type_field: Input type field name used to select articles
            type_value: Type value eligible for classification
            class_field: Output field name for ad/non-ad classification
            classifier_batch_size: Number of texts per classifier call
            pipeline_diagnostics: Enable diagnostics on classifier pipeline
            pipeline_precision: Precision forwarded to the pipeline
            progress_every: Progress log cadence for classified records
            log_level: Logging level
            log_file: Optional log destination
        """
        self.input_file = input_file
        self.output_file = output_file
        self.id_field = id_field
        self.text_field = text_field
        self.type_field = type_field
        self.type_value = as_str(type_value)
        self.class_field = class_field
        self.progress_every = progress_every
        self.log_level = log_level
        self.log_file = log_file
        self.classifier_config = ClassifierConfig(
            diagnostics=pipeline_diagnostics,
            precision=pipeline_precision,
            batch_size=classifier_batch_size,
        )
        self.pipeline: Optional[Any] = None
        self.next_progress_log = progress_every

        setup_logging(self.log_level, self.log_file, logger=log)

    def run(self) -> None:
        """Read input, classify eligible rows, and write JSONL output."""
        stats: Dict[str, int] = {
            "total_lines": 0,
            "classified_records": 0,
            "invalid_json": 0,
            "passthrough_non_articles": 0,
            "skipped_missing_id": 0,
            "skipped_missing_text": 0,
        }
        pending: List[Tuple[str, str, str]] = []

        ensure_local_parent(self.output_file)

        log.info("Input: %s", self.input_file)
        log.info("Output: %s", self.output_file)
        log.info(
            "Filtering/classification: %s == %s, text_field=%s, batch_size=%d",
            self.type_field,
            self.type_value,
            self.text_field,
            self.classifier_config.batch_size,
        )

        try:
            with smart_open(
                self.input_file,
                "rt",
                encoding="utf-8",
                transport_params=get_transport_params(self.input_file),
            ) as input_stream, smart_open(
                self.output_file,
                "wt",
                encoding="utf-8",
                transport_params=get_transport_params(self.output_file),
            ) as output_stream:
                for line_number, raw_line in enumerate(input_stream, start=1):
                    line = raw_line.strip()
                    if not line:
                        continue

                    stats["total_lines"] += 1
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        stats["invalid_json"] += 1
                        log.warning("Skipping invalid JSON at line %d", line_number)
                        continue

                    self.process_record(record, output_stream, pending, stats)

                self.flush_batch(output_stream, pending, stats)
        except Exception as exc:
            log.error("Error processing file: %s", exc, exc_info=True)
            sys.exit(1)

        log.info(
            (
                "Done. total_lines=%d classified=%d passthrough_non_articles=%d "
                "skipped_missing_id=%d skipped_missing_text=%d invalid_json=%d"
            ),
            stats["total_lines"],
            stats["classified_records"],
            stats["passthrough_non_articles"],
            stats["skipped_missing_id"],
            stats["skipped_missing_text"],
            stats["invalid_json"],
        )

    def process_record(
        self,
        record: Dict[str, Any],
        output_stream: TextIO,
        pending: List[Tuple[str, str, str]],
        stats: Dict[str, int],
    ) -> None:
        """Process a single parsed JSON record."""
        record_id = self.extract_record_id(record)
        if not record_id:
            stats["skipped_missing_id"] += 1
            return

        record_type = as_str(record.get(self.type_field))
        if record_type != self.type_value:
            if pending:
                self.flush_batch(output_stream, pending, stats)
            output_stream.write(
                json.dumps(
                    {
                        "id": record_id,
                        "tp": record_type,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            stats["passthrough_non_articles"] += 1
            return

        text = as_str(record.get(self.text_field))
        if not text:
            stats["skipped_missing_text"] += 1
            return

        pending.append((record_id, record_type, text))
        if len(pending) >= self.classifier_config.batch_size:
            self.flush_batch(output_stream, pending, stats)

    def extract_record_id(self, record: Dict[str, Any]) -> str:
        """Extract an ID with a fallback to `c_id` for legacy-style input rows."""
        record_id = as_str(record.get(self.id_field))
        if record_id:
            return record_id

        if self.id_field != "c_id":
            return as_str(record.get("c_id"))

        return ""

    def flush_batch(
        self,
        output_stream: TextIO,
        pending: List[Tuple[str, str, str]],
        stats: Dict[str, int],
    ) -> None:
        """Classify and write the current batch, if any."""
        if not pending:
            return

        classified = self.classify_batch(pending)
        for record in classified:
            output_stream.write(json.dumps(record, ensure_ascii=False) + "\n")

        stats["classified_records"] += len(classified)
        pending.clear()
        self.log_progress(stats)

    def classify_batch(
        self,
        records: Sequence[Tuple[str, str, str]],
    ) -> List[Dict[str, str]]:
        """Classify a batch of (id, tp, text) tuples."""
        texts = [text for _, _, text in records]
        outputs = _pipeline_predict_batch(
            pipeline=self.get_pipeline(),
            texts=texts,
            precision=self.classifier_config.precision,
        )

        if len(outputs) != len(records):
            raise RuntimeError(
                f"Classifier returned {len(outputs)} results for {len(records)} inputs"
            )

        classified: List[Dict[str, str]] = []
        for (record_id, record_type, _text), output in zip(records, outputs):
            type_label = _extract_type_label_from_output(output)
            if not type_label:
                raise RuntimeError(
                    "Classifier output is missing required 'type' field for "
                    f"record id={record_id}"
                )

            final_label = type_label.lower()
            if final_label not in {DEFAULT_AD_VALUE, DEFAULT_NON_AD_VALUE}:
                raise RuntimeError(
                    "Unexpected classifier 'type' value "
                    f"'{type_label}' for record id={record_id}"
                )

            classified.append(
                {
                    "id": record_id,
                    "tp": record_type,
                    self.class_field: final_label,
                }
            )

        return classified

    def get_pipeline(self) -> Any:
        """Build the classifier lazily so passthrough-only inputs still work."""
        if self.pipeline is None:
            self.pipeline = self.build_ad_classifier()
        return self.pipeline

    def build_ad_classifier(self) -> Any:
        """Instantiate the impresso internal ad classifier pipeline."""
        try:
            from impresso_pipelines.adclassifier import AdClassifierPipeline  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Could not import impresso internal ad classifier. "
                "Install with: pip install 'impresso-pipelines[adclassifier]'"
            ) from exc

        return AdClassifierPipeline(diagnostics=self.classifier_config.diagnostics)

    def log_progress(self, stats: Dict[str, int]) -> None:
        """Emit progress logs when the classified count crosses the next threshold."""
        if stats["classified_records"] < self.next_progress_log:
            return

        log.info(
            "Progress: classified=%d passthrough_non_articles=%d invalid_json=%d",
            stats["classified_records"],
            stats["passthrough_non_articles"],
            stats["invalid_json"],
        )
        while stats["classified_records"] >= self.next_progress_log:
            self.next_progress_log += self.progress_every


def main(args: Optional[List[str]] = None) -> None:
    """
    Main function to run the content item classification processor.

    Args:
        args: Command-line arguments (uses sys.argv if None)
    """
    options = parse_arguments(args)

    processor = ContentItemClassificationProcessor(
        input_file=options.input,
        output_file=options.output,
        id_field=options.id_field,
        text_field=options.text_field,
        type_field=options.type_field,
        type_value=options.type_value,
        class_field=options.class_field,
        classifier_batch_size=options.classifier_batch_size,
        pipeline_diagnostics=options.pipeline_diagnostics,
        pipeline_precision=options.pipeline_precision,
        progress_every=options.progress_every,
        log_level=options.log_level,
        log_file=options.log_file,
    )

    log.info("%s", options)
    processor.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log.error("Processing error: %s", exc, exc_info=True)
        sys.exit(2)
