import sublime, sublime_plugin

_TRANSITION_CURSOR_SCOPE_TYPE = 'transition_cursor'
_TRANSITION_CURSOR_ICON       = 'dot'
_TRANSITION_CURSOR_FLAGS      = sublime.DRAW_EMPTY | sublime.DRAW_NO_FILL | sublime.PERSISTENT


#### Helper functions for adding and restoring selections ####

def set_transition_sels(view, sels):
    """Set the updated transition selections and marks.
    """
    view.add_regions("transition_sels", sels,
                     scope = _TRANSITION_CURSOR_SCOPE_TYPE,
                     icon  = _TRANSITION_CURSOR_ICON,
                     flags = _TRANSITION_CURSOR_FLAGS)

def find_prev_sel(trans_sels, current_sel):
    """Find the region in `trans_sels` that is right before `current_sel`.
    Assume `trans_sels` is sorted.
    """
    for i in range(len(trans_sels) - 1, -1, -1):
        if trans_sels[i].begin() < current_sel.begin():
            return i, trans_sels[i]

    # Rotate to the last if `current_sel` is before all other selections
    return -1, trans_sels[-1]

def find_next_sel(trans_sels, current_sel):
    """Find the region in `trans_sels` that is right after `current_sel`.
    Assume `trans_sels` is sorted.
    """
    for i, sel in enumerate(trans_sels):
        if sel.end() > current_sel.end():
            return i, trans_sels[i]

    # Rotate to the beginning if `current_sel` is after all other selections
    return 0, trans_sels[0]


#### Commands ####

class PowerCursorAddCommand(sublime_plugin.TextCommand):
    """Add a new transition cursor in the view.
    """
    def run(self, edit, keep_alive_cursor_index = -1, keep_alive_cursor_position = "b"):
        view = self.view

        # Store the current selection
        current_sels = [s for s in view.sel()]
        trans_sels = view.get_regions("transition_sels")
        trans_sels.extend(current_sels)
        set_transition_sels(view, trans_sels)

        # Keep one current cursor alive, depending on the given args
        view.erase_regions("mark")
        view.sel().clear()
        try:
            alive_sel = current_sels[keep_alive_cursor_index]
            alive_pos = {
                "a": alive_sel.a,
                "b": alive_sel.b,
                "begin": alive_sel.begin(),
                "end": alive_sel.end(),
            }[keep_alive_cursor_position]
        except Exception:
            # Fail safe
            alive_sel = current_sels[-1]
            alive_pos = alive_sel.b

        view.sel().add(sublime.Region(alive_pos, alive_pos))

class PowerCursorRemoveCommand(sublime_plugin.TextCommand):
    """Remove the current transition cursor and switch back to the previous one.
    """
    def run(self, edit):
        view = self.view

        # Retrieve the transition selections
        trans_sels = view.get_regions("transition_sels")
        if len(trans_sels) == 0:
            return

        # Activate the selection that is closest to the current selection(s)
        # in terms of lines
        last_index, last_sel = find_prev_sel(trans_sels, view.sel()[0])
        next_index, next_sel = find_next_sel(trans_sels, view.sel()[-1])

        last_row, last_col = view.rowcol(last_sel.end())
        next_row, next_col = view.rowcol(next_sel.begin())
        start_row, start_col = view.rowcol(view.sel()[0].begin())
        end_row, end_col = view.rowcol(view.sel()[-1].end())
        if abs(start_row - last_row) < abs(next_row - end_row):
            index, new_sel = last_index, last_sel
        else:
            index, new_sel = next_index, next_sel

        view.sel().clear()
        view.sel().add(new_sel)
        view.show(new_sel)
        if new_sel.a != new_sel.b:
            view.add_regions("mark", [sublime.Region(last_sel.a, last_sel.a)],
                             "mark", "", sublime.HIDDEN | sublime.PERSISTENT)
        else:
            view.erase_regions("mark")

        del(trans_sels[index])
        set_transition_sels(view, trans_sels)

class PowerCursorSelectCommand(sublime_plugin.TextCommand):
    """Switch back and forth between transition cursors.
    """
    def run(self, edit, forward = False):
        view = self.view

        # Add the current selections into the transition lists
        current_sels = [s for s in view.sel()]
        trans_sels = view.get_regions("transition_sels")
        trans_sels.extend(current_sels)

        # Lazy step: Store the disorganized region and retrieve a sorted and
        # merged region list
        view.add_regions("transition_sels", trans_sels)
        trans_sels = view.get_regions("transition_sels")

        # Get the previous or next selection and mark
        if forward:
            index, sel = find_next_sel(trans_sels, current_sels[-1])
        else:
            index, sel = find_prev_sel(trans_sels, current_sels[0])

        # Activate the selection
        view.sel().clear()
        view.sel().add(sel)
        view.show(sel)
        if sel.a != sel.b:
            view.add_regions("mark", [sublime.Region(sel.a, sel.a)],
                             "mark", "", sublime.HIDDEN | sublime.PERSISTENT)

        # Remove it from transition list
        del(trans_sels[index])
        set_transition_sels(view, trans_sels)

class PowerCursorActivateCommand(sublime_plugin.TextCommand):
    """Activate all cursors (including the one that's currently alive).
    """
    def run(self, edit):
        view = self.view
        sels = view.get_regions("transition_sels")
        view.sel().add_all(sels)
        view.erase_regions("transition_sels")
        view.erase_regions("mark")

class PowerCursorExitCommand(sublime_plugin.TextCommand):
    """Clear all transition cursors and exit the transition state.
    """
    def run(self, edit):
        self.view.erase_regions("transition_sels")


class CursorTransitionListener(sublime_plugin.EventListener):
    """Provide the transition status for context queries.
    """
    def on_query_context(self, view, key, operator, operand, match_all):
        if key == 'in_cursor_transition':
            in_transition = len(view.get_regions("transition_sels")) > 0
            return in_transition == operand if operator == sublime.OP_EQUAL else in_transition
