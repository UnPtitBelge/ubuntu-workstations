function fish_user_key_bindings --description 'Additional word editing shortcuts'
    # Fish normally supports Ctrl+Delete, but bind it explicitly here.
    bind ctrl-delete kill-word
    bind ctrl-backspace backward-kill-word
    # The Ghostty fallback sends the same sequence as Alt+Backspace.
    bind alt-backspace backward-kill-word
end
