# Institutional Scope Note

[Development notes](development-en.md) | [Known limitations](https://gasyoun.github.io/IndologyScholars/known-limitations.html)

The first PPV article does not make institution-level structural claims unless
the claim can be supported by source-backed institutional evidence. Conference
programmes often publish a city label where an institution would normally
appear, especially in the Zograf series. A city marker is therefore treated as
public programme representation, not employment.

## What Is In Scope

- raw affiliation strings as published in programmes;
- city-only labels as evidence of programme format and public visibility;
- source-backed dated institutional spans in
  `curation/verified_affiliation_spans.csv`;
- cautiously normalized organization pages for navigation, where the source
  label or verified span supports the normalization.

## What Is Out Of Scope

- claims that a city-only participant has no institution;
- claims about complete institutional productivity or institutional dominance;
- automatic continuation of an affiliation beyond its dated evidence unless it
  is visibly marked as tentative;
- interpreting regional or peripheral labels as professional weakness.

## Practical Rule

If an institutional claim cannot be traced to a programme field, authority
record, or `verified_affiliation_spans.csv`, keep it as a question for future
curation rather than an article result.
