function gl --description 'Git log, concise graph'
    command git log --oneline --graph $argv
end
