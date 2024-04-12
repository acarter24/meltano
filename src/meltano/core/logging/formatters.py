"""Various utils and formatters for log rendering control."""

from __future__ import annotations

import typing as t

import click
import structlog
from rich.console import Console
from rich.traceback import Traceback, install

from meltano.core.utils import get_no_color_flag

if t.TYPE_CHECKING:
    from types import TracebackType

    from structlog.types import Processor

install(suppress=[click])

TIMESTAMPER = structlog.processors.TimeStamper(fmt="iso")

LEVELED_TIMESTAMPED_PRE_CHAIN: t.Sequence[Processor] = (
    # Add the log level and a timestamp to the event_dict if the log entry
    # is not from structlog.
    structlog.stdlib.add_log_level,
    TIMESTAMPER,
)


def rich_exception_formatter_factory(
    color_system: t.Literal["auto", "standard", "256", "truecolor", "windows"] = "auto",
    no_color: bool | None = None,
    show_locals: bool = False,
) -> t.Callable[[t.TextIO, structlog.types.ExcInfo], None]:
    """Create an exception formatter for logging using the rich package.

    Examples:
    >>> rich_traceback = rich_exception_formatter_factory(color_system="truecolor")
    >>> plane_rich_traceback = rich_exception_formatter_factory(no_color=True)

    Args:
        color_system: The color system supported by your terminal.
        no_color: Enabled no color mode, or None to auto detect. Defaults to None.
        show_locals: Whether to show local variables in the traceback.

    Returns:
        Exception formatter function.
    """

    def _traceback(
        sio,
        exc_info: tuple[type[t.Any], BaseException, TracebackType | None],
    ) -> None:
        sio.write("\n")
        Console(file=sio, color_system=color_system, no_color=no_color).print(
            Traceback.from_exception(
                *exc_info,
                show_locals=show_locals,
            ),
        )

    return _traceback


def _process_formatter(
    processor: Processor,
    *,
    include_callsite_parameters: bool = False,
) -> structlog.stdlib.ProcessorFormatter:
    """Use _process_formatter to configure a structlog.stdlib.ProcessFormatter.

    It will automatically add log level and timestamp fields to any log entries
    not originating from structlog.

    Args:
        processor: A structlog message processor such as
            `structlog.dev.ConsoleRenderer`.
        include_callsite_parameters: Whether to include callsite parameters in
            the output.

    Returns:
        A configured log processor.
    """
    foreign_pre_chain = LEVELED_TIMESTAMPED_PRE_CHAIN

    if include_callsite_parameters:
        foreign_pre_chain = (  # noqa: WPS434
            *foreign_pre_chain,
            structlog.processors.CallsiteParameterAdder(
                # Most folks probably don't need thread and process process IDs, so
                # these three should be enough to start with.
                parameters=(
                    structlog.processors.CallsiteParameter.PATHNAME,
                    structlog.processors.CallsiteParameter.LINENO,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                ),
            ),
        )

    return structlog.stdlib.ProcessorFormatter(
        processor=processor,
        foreign_pre_chain=foreign_pre_chain,
    )


def console_log_formatter(
    colors: bool = False,
    show_locals: bool = False,
    include_callsite_parameters: bool = False,
) -> structlog.stdlib.ProcessorFormatter:
    """Create a logging formatter for console rendering that supports colorization.

    Args:
        colors: Add color to output.
        show_locals: Whether to show local variables in the traceback.
        include_callsite_parameters: Whether to include callsite parameters in
            the console output.

    Returns:
        A configured console log formatter.
    """
    colors = colors and not get_no_color_flag()

    if colors:
        exception_formatter = rich_exception_formatter_factory(
            color_system="truecolor",
            show_locals=show_locals,
        )
    else:
        exception_formatter = rich_exception_formatter_factory(
            no_color=True,
            show_locals=show_locals,
        )

    return _process_formatter(
        structlog.dev.ConsoleRenderer(
            colors=colors,
            exception_formatter=exception_formatter,
        ),
        include_callsite_parameters=include_callsite_parameters,
    )


def key_value_formatter(
    sort_keys: bool = False,
    key_order: t.Sequence[str] | None = None,
    drop_missing: bool = False,
    *,
    include_callsite_parameters: bool = False,
) -> structlog.stdlib.ProcessorFormatter:
    """Create a logging formatter that renders lines in key=value format.

    Args:
        sort_keys: Whether to sort keys when formatting.
        key_order: List of keys that should be rendered in this exact order.
            Missing keys will be rendered as None, extra keys depending on
            *sort_keys* and the dict class.
        drop_missing: When True, extra keys in *key_order* will be dropped
            rather than rendered as None.
        include_callsite_parameters: Whether to include callsite parameters in
            the key=value output.

    Returns:
        A configured key=value formatter.
    """
    return _process_formatter(
        processor=structlog.processors.KeyValueRenderer(
            sort_keys=sort_keys,
            key_order=key_order,
            drop_missing=drop_missing,
        ),
        include_callsite_parameters=include_callsite_parameters,
    )


def json_formatter(
    *,
    include_callsite_parameters: bool = False,
) -> structlog.stdlib.ProcessorFormatter:
    """Create a logging formatter that renders lines in JSON format.

    Args:
        include_callsite_parameters: Whether to include callsite parameters in
            the JSON output.

    Returns:
        A configured JSON formatter.
    """
    return _process_formatter(
        processor=structlog.processors.JSONRenderer(),
        include_callsite_parameters=include_callsite_parameters,
    )
