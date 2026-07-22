#set page(
  paper: "a4",
  flipped: true,
  margin: 12mm,
)

#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node
#import fletcher.shapes: cylinder

#set text(
  font: "Libertinus Serif",
  size: 9pt,
)

#let source-style = (
  fill: rgb("#eef4ff"),
  stroke: rgb("#315b96"),
  corner-radius: 4pt,
  inset: 10pt,
)

#let process-style = (
  fill: rgb("#f7f7f7"),
  stroke: rgb("#555555"),
  corner-radius: 4pt,
  inset: 10pt,
)

#let check-style = (
  fill: rgb("#fff7df"),
  stroke: rgb("#a36b00"),
  corner-radius: 4pt,
  inset: 10pt,
)

#let data-style = (
  fill: rgb("#edf8ef"),
  stroke: rgb("#397847"),
  inset: 10pt,
)

#figure(
  diagram(
    spacing: (22mm, 18mm),
    node-stroke: 0.8pt,
    edge-stroke: 0.9pt,
    edge-corner-radius: 4pt,

    // Sources
    node(
      (0, 0),
      name: <historical-source>,
      align(center)[
        *Historical polling data* \
        Before 2005 \
        #text(size: 8pt, fill: gray)[Kayser et al.]
      ],
      ..source-style,
      width: 43mm,
    ),

    node(
      (0, 2),
      name: <wahlrecht>,
      align(center)[
        *Wahlrecht.de* \
        Polling data from 2005 onward \
        #text(size: 8pt, fill: gray)[Primary data source]
      ],
      ..source-style,
      width: 43mm,
    ),

    node(
      (0, 4),
      name: <dawum>,
      align(center)[
        *DAWUM* \
        Supplementary polling data
      ],
      ..source-style,
      width: 43mm,
    ),

    // Ingestion
    node(
      (2, 2),
      name: <ingestion>,
      align(center)[
        *Data ingestion* \
        Parse and normalize \
        source-specific records
      ],
      ..process-style,
      width: 39mm,
    ),

    edge(
      <historical-source>,
      <ingestion>,
      "->",
      label: [historical import],
      label-pos: 0.42,
    ),

    edge(
      <wahlrecht>,
      <ingestion>,
      "->",
      label: [primary import],
      label-pos: 0.42,
    ),

    edge(
      <dawum>,
      <ingestion>,
      "->",
      label: [supplement],
      label-pos: 0.42,
    ),

    // Quality control
    node(
      (4, 0),
      name: <plausibility>,
      align(center)[
        *Plausibility check* \
        Validate realistic \
        percentage changes
      ],
      ..check-style,
      width: 39mm,
    ),

    node(
      (4, 2),
      name: <deduplication>,
      align(center)[
        *Duplicate detection* \
        Identify overlapping or \
        identical poll releases
      ],
      ..check-style,
      width: 39mm,
    ),

    node(
      (4, 4),
      name: <selection>,
      align(center)[
        *Quality selection* \
        Retain the best-quality \
        version of each poll
      ],
      ..check-style,
      width: 39mm,
    ),

    edge(
      <ingestion>,
      <plausibility>,
      "->",
    ),

    edge(
      <plausibility>,
      <deduplication>,
      "->",
    ),

    edge(
      <deduplication>,
      <selection>,
      "->",
    ),

    // Storage
    node(
      (6, 2),
      name: <database>,
      align(center)[
        *Polling database* \
        Validated and canonical \
        polling observations
      ],
      shape: cylinder,
      ..data-style,
      width: 42mm,
      height: 23mm,
    ),

    node(
      (8, 2),
      name: <api>,
      align(center)[
        *Polling API* \
        Query, filter and return \
        standardized poll data
      ],
      fill: rgb("#f2edff"),
      stroke: rgb("#6948a5"),
      corner-radius: 4pt,
      inset: 10pt,
      width: 40mm,
    ),

    edge(
      <selection>,
      <database>,
      "->",
      label: [accepted record],
      label-pos: 0.48,
    ),

    edge(
      <database>,
      <api>,
      "->",
      label: [validated data],
      label-pos: 0.5,
    ),
  ),
  caption: [
    Data ingestion and quality-control pipeline of the zweitstimme.org polling-api.
  ],
)
