# DICOM viewer

A Vite/Vue app embedded by **Imaging Study** to display a series.

## Building

```bash
cd viewer
yarn install
yarn build
```

`vite.config.js` writes the build to `healthcare/public/viewer` with base
`/assets/healthcare/viewer/`, which is where Frappe serves it from and where
`imaging_study.js` loads it. The output is not committed, so a fresh clone has no
viewer until this is run — `bench build` does not cover it.
