# Slide anatomy

How notebook cells map to reveal.js slides.

## The five `slide_type` values

A cell's `slideshow.slide_type` metadata field controls its role. Values:

### `slide`
Starts a new horizontal slide. The audience navigates between `slide` cells with the right/left arrows or space.

Use for: top-level section breaks, each major beat in the story.

### `subslide`
Stacks vertically below the current `slide`. The audience presses ↓ to descend into them, ↑ to come back up.

Use for: supporting detail behind a top-level point. Audiences who don't want the detail can keep pressing → and skip the column entirely. Useful for backup slides, alternative views of the same data, or appendix material.

### `fragment`
Appears on the next click inside the current slide. Fragments stack — three `fragment` cells in a row means three clicks to reveal all three.

Use for: progressive reveals. The headline appears first, then a chart, then a caveat. Or three competing explanations of a pattern, revealed one at a time.

### `skip`
Excluded from the deck entirely. Cell stays in the notebook (so you keep the analysis) but never appears in the slides.

Use for: data prep, sanity checks, dataframe `.head()` calls — work the audience doesn't need to see.

### `notes`
Speaker notes. Visible only in speaker view (press `s` in the deck), never to the audience.

Use for: timing cues, anticipated questions, the longer explanation behind the slide's headline. Markdown is rendered.

### Unset (no `slide_type`)
The cell *continues the current slide*. This is the common case for code cells whose output (a chart, a table) belongs visually under the markdown heading above.

So the typical pattern is:

```
[slide]      ## What changed
[unset]      df_summary = ...
[unset]      fig = px.bar(df_summary, ...); fig.show()
```

Three cells, one slide.

## Layout reality check

Reveal's default slide container is roughly **960×700 pixels**. Plan content to fit:

- One headline + one chart (~900×520) + ~80px of margin = comfortable.
- Two charts side-by-side requires either `subplot_titles` and a single Plotly figure, or HTML tricks. Don't try to pack two separate `fig.show()` calls into one slide expecting columns — they stack vertically and overflow.
- Long bullet lists overflow. Either trim, or set `--no-scroll=False` (default) and let reveal handle it.

## Vertical columns: when to use subslides

Subslides are a navigation aid, not a layout tool. Use them when there's optional depth: "here's the headline; press down if you want the breakdown by segment, otherwise press right." They're invisible to anyone who doesn't go looking. If everyone needs to see the content, make it a regular `slide`.

## Authoring rhythm

A common structure for a 20-slide analysis readout:

| Section            | Slides | Pattern                                |
|--------------------|--------|----------------------------------------|
| Title + framing    | 2      | `slide` × 2                            |
| Method overview    | 1 + 3  | `slide` + 3 `subslide` (optional depth)|
| Finding 1          | 1 + 1  | `slide` (headline) + unset (chart)     |
| Finding 2          | 1 + 1  | same                                   |
| Finding 3          | 1 + 1  | same                                   |
| Caveats            | 1      | `slide`                                |
| Recommendations    | 1      | `slide` (uses `fragment` for reveals)  |
| Appendix           | N      | `subslide`s, audience skips by default |

Speaker notes (`notes`) live alongside any slide where you want the longer story available to yourself but not on screen.

## When the auto-tagger gets it wrong

`scripts/tag_slides.py --auto` is a heuristic, not a parser. It maps `#`/`##` headings to `slide`/`subslide`, which works ~80% of the time. The other 20%:

- You used `#` for emphasis, not section break. Override that cell's tag in a manifest, or change the heading.
- You want a chart on its own slide. The markdown heading approach assumes "heading then chart"; if the chart deserves a dedicated slide, add a one-line heading or tag the code cell explicitly.
- You want fragments. Auto-tag doesn't infer these — apply them via manifest.
