function ls --description 'Directory listing; use eza if installed'
    if command -q eza
        command eza --group-directories-first $argv
    else
        command ls $argv
    end
end
