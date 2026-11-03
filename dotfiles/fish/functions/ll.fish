function ll --description 'Long directory listing'
    if command -q eza
        command eza -lah --group-directories-first $argv
    else
        command ls -lah $argv
    end
end
