#let report = json(bytes(sys.inputs.report))

#set document(title: report.title)
#set page(paper: "a4", margin: 18mm)
#set text(font: "Libertinus Serif", size: 10pt)
#show heading: set text(font: "Libertinus Serif")
#import "./flowchart.typ": polling-api-flowchart

#let value-table(..items) = table(
  columns: (42%, 58%),
  inset: 6pt,
  stroke: 0.5pt + gray,
  ..items,
)

#let empty-or-list(items) = {
  if items.len() == 0 {
    [No quality checks need review.]
  } else {
    for item in items {
      [- #raw(item.name): #item.failed]
    }
  }
}

= #raw(report.title)

Generated: #raw(report.generated_at) \
API version: #raw(report.api_version)

== Pipeline Run

#value-table(
  [Run ID],
  [#raw(report.run.run_id)],
  [Success],
  [#raw(report.run.success)],
  [Started],
  [#raw(report.run.started_at)],
  [Finished],
  [#raw(report.run.finished_at)],
  [Duration],
  [#raw(report.run.duration)],
  [Scraped polls],
  [#report.run.scraped],
  [Created / updated],
  [#report.run.created / #report.run.updated],
  [Processing issues],
  [#report.run.errors],
)

== Data Quality Summary

#value-table(
  [Status],
  [#raw(report.totals.status)],
  [Total polls],
  [#report.totals.polls],
  [Validated polls],
  [#report.totals.validated_polls],
  [Research-ready polls],
  [#report.totals.valid_polls (#raw(report.totals.valid_share))],
  [Polls outside quality criteria],
  [#report.totals.invalid_polls],
  [Polls with review notes],
  [#report.totals.warning_polls],
  [Latest validation],
  [#raw(report.totals.latest_validated_at)],
)

== Primary Sources by Year

#table(
  columns: (10%, 14%, 16%, 42%, 18%),
  inset: 3pt,
  stroke: 0.4pt + gray,
  table.header(
    [Year],
    [Polls],
    [Validated],
    [Primary source],
    [Primary polls],
  ),
  for year in report.years {
    [#year.year]
    [#year.total_polls]
    [#year.validated_polls]
    [#raw(year.primary_provider) \ #raw(year.primary_source)]
    [#year.primary_polls]
  },
)

== Validation Checks

#table(
  columns: (45%, 18%, 18%, 19%),
  inset: 5pt,
  stroke: 0.4pt + gray,
  table.header([Check], [Passed], [Needs review], [Pass share]),
  for check in report.checks {
    [#raw(check.name)]
    [#check.passed]
    [#check.failed]
    [#raw(check.pass_share)]
  },
)

== Most Common Quality Flags

#empty-or-list(report.top_failures)

== Data Flowchart


#polling-api-flowchart()
