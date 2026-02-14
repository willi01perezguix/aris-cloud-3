from aris_control_2.app.ui.pagination import PaginationState, goto_page, next_page, prev_page


def test_pagination_next_prev_goto_bounds() -> None:
    state = PaginationState(page=1, page_size=20)

    next_page(state, has_next=True)
    assert state.page == 2

    prev_page(state)
    assert state.page == 1

    prev_page(state)
    assert state.page == 1

    goto_page(state, 0)
    assert state.page == 1

    next_page(state, has_next=False)
    assert state.page == 1
