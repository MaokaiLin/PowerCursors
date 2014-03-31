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
        if trans_sels[i].a < current_sel.a:
            return i, trans_sels[i]
    return -1, trans_sels[-1]  # Rotate to the last if `current_sel` is before of all other selections

def find_next_sel(trans_sels, current_sel):
    """Find the region in `trans_sels` that is right after `current_sel`.
    Assume `trans_sels` is sorted.
    """
    for i, sel in enumerate(trans_sels):
        if sel.a > current_sel.a:
            return i, trans_sels[i]
    return 0, trans_sels[0]  # Rotate to the beginning if `current_sel` is after of all other selections


#### Command functions ####

class PowerCursorAddCommand(sublime_plugin.TextCommand):
    """Add a new transition cursor in the view.
    """
    def run(self, edit, keep_alive_cursor_index = -1, keep_alive_cursor_position = "b"):
        # Store the current selection
        current_sels = [s for s in self.view.sel()]
        trans_sels = self.view.get_regions("transition_sels")
        trans_sels.extend(current_sels)
        set_transition_sels(self.view, trans_sels)

        # Keep one current cursor alive, depending on the given args
        self.view.erase_regions("mark")
        self.view.sel().clear()
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

        self.view.sel().add(sublime.Region(alive_pos, alive_pos))

class PowerCursorRemoveCommand(sublime_plugin.TextCommand):
    """Remove the current transition cursor and switch back to the previous one.
    """
    def run(self, edit):
        # Retrieve the transition selections
        trans_sels = self.view.get_regions("transition_sels")
        if len(trans_sels) == 0:
            return

        # Activate the selection right before the current cursor
        index, last_sel = find_prev_sel(trans_sels, self.view.sel()[0])
        self.view.sel().clear()
        self.view.sel().add(last_sel)
        if last_sel.a != last_sel.b:
            self.view.add_regions("mark", [sublime.Region(last_sel.a, last_sel.a)],
                                  "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)
        else:
            self.view.erase_regions("mark")

        del(trans_sels[index])
        set_transition_sels(self.view, trans_sels)

class PowerCursorSelectCommand(sublime_plugin.TextCommand):
    """Switch back and forth between transition cursors.
    """
    def run(self, edit, forward = False):
        # Add the current selections into the transition lists
        current_sels = [s for s in self.view.sel()]
        trans_sels = self.view.get_regions("transition_sels")
        trans_sels.extend(current_sels)

        # Lazy step: set and retrieve a sorted and merged region list
        self.view.add_regions("transition_sels", trans_sels)
        trans_sels = self.view.get_regions("transition_sels")

        # Get the previous or next selection and mark
        if forward:
            index, sel = find_next_sel(trans_sels, current_sels[-1])
        else:
            index, sel = find_prev_sel(trans_sels, current_sels[0])

        # Activate the selection
        self.view.sel().clear()
        self.view.sel().add(sel)
        self.view.show(sel)
        if sel.a != sel.b:
            self.view.add_regions("mark", [sublime.Region(sel.a, sel.a)],
                                  "mark", "dot", sublime.HIDDEN | sublime.PERSISTENT)

        # Remove it from transition list
        del(trans_sels[index])
        set_transition_sels(self.view, trans_sels)

class PowerCursorsActivateCommand(sublime_plugin.TextCommand):
    """Activate all cursors (including the current one).
    """
    def run(self, edit):
        sels = self.view.get_regions("transition_sels")
        self.view.sel().add_all(sels)
        self.view.erase_regions("transition_sels")
        self.view.erase_regions("mark")

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
