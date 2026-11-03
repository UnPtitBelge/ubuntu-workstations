function md --description 'Markdown pager using glow'
    if command -q glow
        command glow -p $argv
    else
        echo 'md: glow is not installed' >&2
        return 127
    end
end
