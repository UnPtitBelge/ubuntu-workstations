function la --description 'All files listing'
    if command -q eza
        command eza -la --group-directories-first $argv
    else
        command ls -la $argv
    end
end
