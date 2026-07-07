/**
 * Collection highlights shown under both hero pages. Real FAMSF works; only
 * those with an iiif.famsf.org thumb show a live image (the rest fall back to a
 * "no image yet" mat). Kept in one place so the two heroes stay in sync.
 */
export interface Highlight {
  title: string;
  artist: string;
  date: string;
  thumb: string | null;
}

export const highlights: Highlight[] = [
  {
    title: "Water Lilies",
    artist: "Claude Monet",
    date: "ca. 1914–1917",
    thumb: "https://iiif.famsf.org/iiif/3/MS_97614_20250828-01_Crop/thumb-400.webp",
  },
  {
    title: "Bust of Martin Luther King, Jr.",
    artist: "Elizabeth Catlett",
    date: "ca. 1984",
    thumb: "https://iiif.famsf.org/iiif/3/MS_308677_20241024-03_Crop-2/thumb-400.webp",
  },
  {
    title: "Untitled (Two Figures)",
    artist: "Willem de Kooning",
    date: "ca. 1947",
    thumb: "https://iiif.famsf.org/iiif/3/A076624_V1_crop/thumb-400.webp",
  },
  {
    title: "Untitled (Lafayette Park, San Francisco)",
    artist: "Arnold Genthe",
    date: "1906",
    thumb: "https://iiif.famsf.org/iiif/3/MS_7396_20150414-02/thumb-400.webp",
  },
];
