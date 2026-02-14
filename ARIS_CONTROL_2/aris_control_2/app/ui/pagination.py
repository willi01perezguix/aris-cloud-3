from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaginationState:
    page: int = 1
    page_size: int = 20


def next_page(state: PaginationState, has_next: bool | None) -> PaginationState:
    if has_next is False:
        return state
    state.page += 1
    return state


def prev_page(state: PaginationState) -> PaginationState:
    state.page = max(1, state.page - 1)
    return state


def goto_page(state: PaginationState, page: int) -> PaginationState:
    state.page = max(1, page)
    return state
