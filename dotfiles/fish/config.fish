# Fish workstation configuration — portable and intentionally small.
set -g fish_greeting

# The user's tools (mise, uv, Cargo, etc.) commonly live here.
fish_add_path --path $HOME/.local/bin $HOME/.cargo/bin

if command -q code
    set -gx EDITOR code
else
    set -gx EDITOR nano
end

# Avoid forcing TERM or GTK_IM_MODULE; let Ghostty and the desktop choose.
# Autosuggestions, Tab completion, and history search are native Fish features.

# Keep optional integrations behind availability checks.
if command -q mise
    mise activate fish | source
end

if status is-interactive
    # Work around zoxide compatibility with Fish 4.8
    if command -q zoxide
        if not functions -q __zoxide_cd_internal
            functions cd | string replace -r '^function cd\s' 'function __zoxide_cd_internal ' | source
        end

        zoxide init fish | source
    end

    # Prompt
    if command -q starship
        starship init fish | source
    end
end

# Navigate two directories up
function ...
    builtin cd ../..
end
