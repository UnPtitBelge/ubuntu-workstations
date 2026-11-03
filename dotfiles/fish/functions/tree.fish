function tree --description 'Tree view with eza fallback'
    if command -q eza
        command eza --tree $argv
    else if command -q tree
        command tree $argv
    else
        command find . -print
    end
end
