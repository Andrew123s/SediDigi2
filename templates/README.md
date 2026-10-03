# SediDigi/<folder name>

<short description>

![](./../static/<image filename>)

## Files

- **filename** - decription

## Pinout & Wiring

### <module name>

<pinout>

### Jetson Orin Nano 40-Pin Header (J12)

```
<pinout>
```

### Wiring

<wiring table>

## Software Setup

### Enable ... (jetson-io)

```bash
sudo /opt/nvidia/jetson-io/jetson-io.py
```

- Select "Configure Jetson 40pin Header"
- Select "Configure header pins manually", enable <TODO>
- Ensure that the layout is identical to the header scheme given above
- Save, exit and reboot

### Install Jetson.GPIO and Python dependencies

```bash
sudo apt install python3-pip
sudo pip3 install Jetson.GPIO

sudo apt install <TODO>
```

### Run the demo

```bash
python3 demo.py
```

### Run the <application name>

```bash
<TODO>
```

## Troubleshooting

### <problem>

<solution>

## Notes (optional)

## Roadmap

- [x] <done>
- [ ] <TODO>

## References

- [<reference>](<url>)