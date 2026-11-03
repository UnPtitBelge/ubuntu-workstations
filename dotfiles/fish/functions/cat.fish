function cat --description 'Readable files with bat fallback'
    if command -q bat
        command bat $argv
    else
        command cat $argv
    end
end
