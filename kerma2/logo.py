"""
Preserved ASCII logo for Kerma.

Sourced verbatim from the original kerma.py REPL banner so the greeting
remains consistent between the legacy shell, the new enhanced REPL, and
the GUI's About panel.
"""

# Raw ASCII form — used by the GUI About panel in a monospace label
LOGO_ASCII = r"""
  ╦╔═┌─┐┬─┐┌┬┐┌─┐
  ╠╩╗├┤ ├┬┘│││├─┤
  ╩ ╩└─┘┴└─┴ ┴┴ ┴
"""

TAGLINE = "A Health Physics · Nuclear Engineering toolkit"

# ANSI-coloured form — used by the REPL
BANNER = (
    "\033[1;36m"
    + LOGO_ASCII.rstrip("\n")
    + "\033[0m\n"
    + "  \033[90mKerma v2.0 · " + TAGLINE + "\033[0m\n"
    + "  \033[90mType  help  for commands · Ctrl+D to exit\033[0m\n"
)


def plain_banner() -> str:
    """Colour-free banner (useful for log files / Windows shells)."""
    return LOGO_ASCII + f"  Kerma v2.0 · {TAGLINE}\n"
