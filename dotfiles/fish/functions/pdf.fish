function pdf --description 'Preview a PDF using pdftoppm and timg'
    if test (count $argv) -lt 1 -o (count $argv) -gt 2
        echo 'Usage: pdf FILE.pdf [PAGE]' >&2
        return 2
    end
    for tool in pdftoppm timg
        if not command -q $tool
            echo "pdf: $tool is not installed" >&2
            return 127
        end
    end
    if not test -f "$argv[1]"
        echo "pdf: file not found: $argv[1]" >&2
        return 1
    end
    set -l tmpdir (mktemp -d)
    or return 1
    set -l result 0
    if test (count $argv) -eq 2
        if not string match -qr '^[1-9][0-9]*$' -- "$argv[2]"
            echo 'pdf: PAGE must be a positive integer' >&2
            command rm -rf -- "$tmpdir"
            return 2
        end
        command pdftoppm -f $argv[2] -l $argv[2] -scale-to 1600 -png "$argv[1]" "$tmpdir/page"
        or set result $status
    else
        command pdftoppm -scale-to 1600 -png "$argv[1]" "$tmpdir/page"
        or set result $status
    end
    if test $result -eq 0
        for img in "$tmpdir"/page-*.png
            if test -f "$img"
                command timg -pk -W -- "$img"
                or set result $status
            end
        end
    end
    command rm -rf -- "$tmpdir"
    return $result
end
