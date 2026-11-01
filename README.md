# lxmfnotify

Read lines from stdin, keep the ones that match a list of patterns, and send
them as LXMF messages. It doesn't matter what produced the lines, so
`js8mon ... | lxmfnotify ...` forwards JS8Call messages to a phone running Sideband,
and any other line producer works the same way.

## Install

```
  pip install .
```

or `pipx install .`. Either puts `lxmfnotify` on the PATH. It uses the
host's Reticulum configuration in `~/.reticulum`, or the one given with
`--rnsconfig`, so rnsd's interfaces are its interfaces.

## Usage

Forward every JS8 message heard on 40 m to one phone, as it arrives:

```
  js8mon -card stream /tmp/sdrfanout/7078000.fifo -f 7.078 | lxmfnotify --address 3f2a...
```

Only lines mentioning two callsigns, one message per five minutes, to two
phones:

```
  js8mon ... | lxmfnotify --address 3f2a...,9c1e... --match N0CALL --match W1ABC --interval 300
```

Strip js8mon's columns before sending, with the program below as the pipe:

```
  js8mon ... | lxmfnotify --address 3f2a... --pipe /usr/local/bin/js8mon-parse
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--address HASH[,HASH...]` | required | LXMF destination hashes, 32 hex characters each |
| `--match PATTERN` | none | text a line must contain, repeatable |
| `--match-regex PATTERN` | none | Python regular expression a line must match, repeatable |
| `--match-file PATH` | none | file of patterns, one per line, repeatable. A line written `/like this/` is a regular expression, the rest are text. Blank lines and `#` comments are ignored |
| `--interval SEC` | 0 | 0 sends each result as it arrives, N collects results and sends one message per N seconds |
| `--pipe PATH` | none | script run once per matched line, see below |
| `--propagation-node HASH` | none | LXMF propagation node to use when direct delivery fails |
| `--name NAME` | `lxmfnotify` | display name announced for this sender |
| `--config DIR` | `~/.lxmfnotify` | identity and LXMF storage |
| `--rnsconfig DIR` | `~/.reticulum` | alternative Reticulum config directory |
| `--no-announce` | off | do not announce this sender's address |
| `--verbose` | off | match, send and delivery events on stderr |

A line is sent when any pattern of either kind hits it. With no patterns
every line is sent. Matching is case-sensitive. A line that hits two
patterns is sent once. Nothing is written to stdout.

Messages use direct delivery to each address. With `--propagation-node`, a message
whose direct delivery fails is resent through the node. The sender's address is
announced at startup and then at a random interval between 90 and 300 minutes.

When stdin closes (or SIGTERM or SIGINT are sent), collected results are sent,
pending deliveries get up to 30 seconds, then lxmfnotify exits. A second signal
exits right away.

### Pre-processing

`--pipe PATH` runs the script or program once per matched line, with the line on the scripts
stdin. Its stdout is what gets sent (whitespace is trimmed). Empty
output drops the line, which is how a pipe script can filter messages. A non-zero exit
drops the line, logs the exit code, and the first line of the program's
stderr. A program that runs longer than 10 seconds is killed.

`examples/js8mon-parse` is a pipe script for js8mon lines. It splits the line
into its columns and prints the message as `CALL: TEXT`. Other columns data can easily
be included, for example `$call ($snr dB $mode): $text`.

### Running under systemd

```
[Service]
ExecStart=/bin/sh -c 'js8mon -card stream /tmp/sdrfanout/7078000.fifo -f 7.078 | lxmfnotify --address 3f2a... --interval 60'
Restart=always
RestartSec=5
```

If js8mon exits, lxmfnotify sees EOF, sends what it has, and exits.

## Tests

```
  python3 -m unittest discover -s tests
```

## Acknowledgements

- [Reticulum](https://github.com/markqvist/Reticulum) and [LXMF](https://github.com/markqvist/LXMF) by Mark Qvist
- Claude AI contributed to this project
