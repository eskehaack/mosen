from collections import defaultdict
from math import floor, isclose, isfinite, log10


def format_count_bar_chart(fig, show_x_tick_labels=True):
    fig.update_layout(xaxis_title=None, yaxis_title="amount")
    fig.update_xaxes(showticklabels=show_x_tick_labels)
    fig.update_yaxes(dtick=count_bar_chart_dtick(fig))
    return fig


def count_bar_chart_dtick(fig):
    values = list(_finite_y_values(fig))
    max_value = _max_visible_magnitude(fig)
    if max_value <= 0:
        return 1

    tick = _nice_tick(max_value / 10)
    if all(isclose(value, round(value)) for value in values):
        return max(1, tick)
    return tick


def _max_visible_magnitude(fig):
    if fig.layout.barmode not in {"relative", "stack"}:
        return max((abs(value) for value in _finite_y_values(fig)), default=0)

    totals = defaultdict(float)
    for trace in fig.data:
        if trace.y is None or trace.visible in {False, "legendonly"}:
            continue

        x_values = trace.x
        for index, value in enumerate(trace.y):
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if not isfinite(number):
                continue

            x_value = x_values[index] if x_values is not None else index
            key = str(x_value)
            totals[key] += number

    return max(
        totals.values(),
        default=0,
    )


def _finite_y_values(fig):
    for trace in fig.data:
        if trace.y is None:
            continue

        for value in trace.y:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue

            if isfinite(number):
                yield number


def _nice_tick(raw_tick):
    exponent = floor(log10(raw_tick))
    scale = 10**exponent
    fraction = raw_tick / scale

    if fraction <= 1:
        nice_fraction = 1
    elif fraction <= 2:
        nice_fraction = 2
    elif fraction <= 5:
        nice_fraction = 5
    else:
        nice_fraction = 10

    return nice_fraction * scale
