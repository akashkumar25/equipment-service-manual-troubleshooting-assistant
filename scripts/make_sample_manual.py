"""Generate the fictional sample service manual in data/samples/.

The manual is invented for demos and tests; it is not derived from any real
manufacturer document.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

PAGES = [
    [
        "Model: TX-200 Hydraulic Excavator",
        "Service Manual - Sample Edition",
        "This fictional manual is used to demo and test the troubleshooting assistant.",
    ],
    [
        "Model: TX-200 Hydraulic Excavator",
        "Section 3: Hydraulic System",
        "Fault codes",
        "E101 Hydraulic oil temperature too high",
        "E102 Hydraulic pressure low",
        "E103 Pilot pressure sensor signal out of range",
        "Check oil level first, then inspect the oil cooler for blockage.",
    ],
    [
        "Section 3: Hydraulic System",
        "Troubleshooting E101",
        "1. Stop the engine and let the machine cool for 10 minutes.",
        "2. Check the hydraulic oil level in the sight glass.",
        "3. Clean debris from the oil cooler fins.",
        "4. If E101 persists, replace the cooler fan relay.",
    ],
    [
        "Section 4: Engine",
        "Fault codes",
        "F2040 Coolant temperature high",
        "SPN 100 FMI 3 Engine oil pressure sensor voltage above normal",
        "Do not operate the machine until the cause is found.",
    ],
]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "data" / "samples" / "tx200_sample_manual.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=A4, invariant=1)
    for lines in PAGES:
        y = 800
        for line in lines:
            c.drawString(60, y, line)
            y -= 22
        c.showPage()
    c.save()
    print(out)


if __name__ == "__main__":
    main()
