# PPT Template Guide

The Studio is deliberately template-first: the uploaded PPTX controls the visual identity.

## Required

- The first slide is used as the master/reference slide.
- Each question becomes one cloned slide.
- The template may contain these text tokens:
  - `#QUESTION` → `Q1`, `Q2`, ...
  - `#SUBJECT` → Physics/Chemistry/Mathematics/etc.
  - `#ANSWER` → answer-key value

## Question image placement

For deterministic placement, create a shape on the first slide and rename it:

`QUESTION_IMAGE`

The Studio removes that shape and places the question crop exactly inside its rectangle.

If the named shape is absent, the Studio uses a safe centered image area automatically.

## Design recommendation

Keep the question image area large enough for formulas and diagrams. Avoid putting decorative elements over the image area. Backgrounds, headers, footers, logos and accent lines remain part of the cloned template slide.
