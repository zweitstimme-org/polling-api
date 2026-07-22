#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node
#import fletcher.shapes: cylinder

// Reusable polling API flowchart.
//
// Import it with:
//
//   #import "templates/flowchart.typ": polling-api-flowchart
//
// Insert it with:
//
//   #polling-api-flowchart()
//
// The surrounding document remains portrait.
// Only the diagram itself is rotated by 90 degrees.

#let polling-api-flowchart(
  caption: [Data ingestion and quality-control pipeline of the polling API.],
  scale-factor: 72%,
) = figure(
  placement: none,
  caption: caption,
  align(center)[
    #rotate(
      90deg,
      reflow: true,
      origin: center,
      scale(
        scale-factor,
        reflow: true,
        diagram(
          spacing: (16mm, 14mm),
          node-stroke: 0.8pt,
          edge-stroke: 0.9pt,
          edge-corner-radius: 4pt,

          // ------------------------------------------------------------
          // Data sources
          // ------------------------------------------------------------

          node(
            (0, 0),
            name: <historical-source>,
            width: 38mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#eef4ff"),
            stroke: rgb("#315b96"),
            align(center)[
              *Historical polling data* \
              Before 2005 \
              #text(
                size: 8pt,
                fill: gray,
              )[
                Kayser et al.
              ]
            ],
          ),

          node(
            (0, 2),
            name: <wahlrecht>,
            width: 38mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#eef4ff"),
            stroke: rgb("#315b96"),
            align(center)[
              *Wahlrecht.de* \
              Polling data from 2005 onward \
              #text(
                size: 8pt,
                fill: gray,
              )[
                Primary data source
              ]
            ],
          ),

          node(
            (0, 4),
            name: <dawum>,
            width: 38mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#eef4ff"),
            stroke: rgb("#315b96"),
            align(center)[
              *DAWUM* \
              Supplementary polling data
            ],
          ),

          // ------------------------------------------------------------
          // Data ingestion
          // ------------------------------------------------------------

          node(
            (2, 2),
            name: <ingestion>,
            width: 36mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#f7f7f7"),
            stroke: rgb("#555555"),
            align(center)[
              *Data ingestion* \
              Parse and normalize \
              source-specific records
            ],
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

          // ------------------------------------------------------------
          // Quality control
          // ------------------------------------------------------------

          node(
            (4, 0),
            name: <plausibility>,
            width: 36mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#fff7df"),
            stroke: rgb("#a36b00"),
            align(center)[
              *Plausibility check* \
              Detect unrealistic \
              percentage changes
            ],
          ),

          node(
            (4, 2),
            name: <deduplication>,
            width: 36mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#fff7df"),
            stroke: rgb("#a36b00"),
            align(center)[
              *Duplicate detection* \
              Identify overlapping or \
              identical poll releases
            ],
          ),

          node(
            (4, 4),
            name: <selection>,
            width: 36mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#fff7df"),
            stroke: rgb("#a36b00"),
            align(center)[
              *Quality selection* \
              Retain the best-quality \
              version of each poll
            ],
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

          // ------------------------------------------------------------
          // Database
          // ------------------------------------------------------------

          node(
            (6, 2),
            name: <database>,
            shape: cylinder,
            width: 39mm,
            height: 22mm,
            inset: 8pt,
            fill: rgb("#edf8ef"),
            stroke: rgb("#397847"),
            align(center)[
              *Polling database* \
              Validated and canonical \
              polling observations
            ],
          ),

          edge(
            <selection>,
            <database>,
            "->",
            label: [accepted record],
            label-pos: 0.48,
          ),

          // ------------------------------------------------------------
          // Polling API
          // ------------------------------------------------------------

          node(
            (8, 2),
            name: <api>,
            width: 36mm,
            inset: 8pt,
            corner-radius: 4pt,
            fill: rgb("#f2edff"),
            stroke: rgb("#6948a5"),
            align(center)[
              *Polling API* \
              Query, filter, and return \
              standardized poll data
            ],
          ),

          edge(
            <database>,
            <api>,
            "->",
            label: [validated data],
            label-pos: 0.5,
          ),
        ),
      ),
    )
  ],
)
