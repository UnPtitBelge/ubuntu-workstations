# No completion invokes monitoring helpers or cloud commands.
complete -c workstation -f
complete -c workstation -l help -s h -d 'Show help'
complete -c workstation -l status -d 'Read local status once'
complete -c workstation -l json -d 'Print status JSON; no raw reports or journals'
complete -c workstation -l config -r -d 'Console configuration file'
complete -c workstation -l interval -x -d 'Local observation interval in seconds'
complete -c workstation -l detail -x -a 'health drift backup restore summary updates post-update alerts update-alerts sync apt-lists apt-upgrades other-backup-proton other-backup-rclone other-restore-proton other-restore-rclone' -d 'Read a selected report'
complete -c workstation -l logs -x -a 'health drift backup restore summary updates post-update alerts update-alerts sync apt-lists apt-upgrades other-backup-proton other-backup-rclone other-restore-proton other-restore-rclone' -d 'Read selected local journal'
