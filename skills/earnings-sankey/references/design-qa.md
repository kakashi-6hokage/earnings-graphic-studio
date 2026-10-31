# Visual QA — Amazon editorial benchmark

Compare actual rendered PNG at full size with the user-provided Amazon and Alphabet references, stored in this plugin. Do not copy the original publisher's watermark/footer.

**Hard fails:** wrong numbers, wrong signs, >2 monetary decimal places, no proper horizontal flow, disconnected GAAP paths, overlapping nodes/labels, clipping, 1px mechanical finance ribbons replacing all large bands, major financial stage missing without disclosure, false "financial QA passed" claims.

**Needs visual correction:** logo too small, sparse canvas, narrow plot occupying only a fraction of the design, title looks like a generic dashboard, expense endpoint labels crowded, sudden kinks, ugly detached boxes.

**Review outputs:** ledger reconciliation PASS/FAIL; monetary formatting PASS/FAIL; geometry PASS/FAIL; visual layout PASS/FAIL; visual comparison qualitative verdict; known caveats.

Image generation tools may produce inaccurate text. For accurate final labels, prefer deterministic SVG and PNG export, reserving image generation for supplementary illustrations.
