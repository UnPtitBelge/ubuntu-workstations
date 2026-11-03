## sudo-rs is not compatible with ansible
Switch sudo version when using ansible:

```fish
sudo update-alternatives --set sudo /usr/bin/sudo.ws
```

To come back to the sudo-rs version, do:

```fish
sudo update-alternatives --set sudo /usr/lib/cargo/bin/sudo
```

This is tracked as Ubuntu bug #2122414.
