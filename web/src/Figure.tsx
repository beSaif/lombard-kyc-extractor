import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cx } from "./lib";

/**
 * An image with an optional overlay (positioned in 0..1 fractions of the image), zoomable in a lightbox.
 * `overlay` is rendered both inline and in the lightbox, so hover state shared via the parent works in both.
 */
export function Figure({
  src,
  caption,
  overlay,
  className,
  imgClassName,
  maxH,
  toolbar,
}: {
  src: string | null | undefined;
  caption?: ReactNode;
  overlay?: ReactNode;
  className?: string;
  imgClassName?: string;
  maxH?: number;
  toolbar?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  if (!src) return <div className="rounded border border-dashed border-line p-6 text-center text-[12px] text-faint">no image</div>;
  return (
    <figure className={cx("min-w-0", className)}>
      <div className="group relative overflow-hidden rounded border border-line bg-sunk">
        <div className="relative mx-auto" style={maxH ? { maxHeight: maxH, width: "fit-content" } : undefined}>
          <img
            src={src}
            alt=""
            className={cx("block w-full select-none", overlay ? "" : "cursor-zoom-in", imgClassName)}
            style={maxH ? { maxHeight: maxH, width: "auto", maxWidth: "100%" } : undefined}
            onClick={() => !overlay && setOpen(true)}
            draggable={false}
          />
          {overlay && <div className="absolute inset-0">{overlay}</div>}
        </div>
        <button
          onClick={() => setOpen(true)}
          className="absolute top-1.5 right-1.5 rounded border border-line bg-panel/90 px-1.5 py-0.5 text-[11px] text-muted opacity-80 shadow-sm hover:text-fg group-hover:opacity-100"
          title="Open large (zoomable)"
        >
          ⤢ zoom
        </button>
      </div>
      {caption && <figcaption className="mt-1 text-[11px] text-muted">{caption}</figcaption>}
      {open && <Lightbox src={src} overlay={overlay} caption={caption} toolbar={toolbar} onClose={() => setOpen(false)} />}
    </figure>
  );
}

function Lightbox({
  src,
  overlay,
  caption,
  toolbar,
  onClose,
}: {
  src: string;
  overlay?: ReactNode;
  caption?: ReactNode;
  toolbar?: ReactNode;
  onClose: () => void;
}) {
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(6, +(z + 0.25).toFixed(2)));
      if (e.key === "-") setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)));
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [onClose]);
  return createPortal(
    <div className="fixed inset-0 z-50 flex flex-col bg-black/70" onClick={onClose}>
      <div className="flex items-center gap-3 border-b border-line bg-panel px-4 py-2 text-[12px]" onClick={(e) => e.stopPropagation()}>
        <span className="text-muted">Zoom</span>
        <input type="range" min={0.5} max={6} step={0.25} value={zoom} onChange={(e) => setZoom(+e.target.value)} className="w-56 accent-[var(--accent)]" />
        <span className="mono w-12 tabular">{Math.round(zoom * 100)}%</span>
        {[1, 2, 3].map((z) => (
          <button key={z} className="rounded border border-line px-1.5 text-muted hover:text-fg" onClick={() => setZoom(z)}>
            {z}×
          </button>
        ))}
        {toolbar}
        <span className="ml-2 truncate text-muted">{caption}</span>
        <span className="ml-auto text-faint">+/- to zoom, Esc to close</span>
        <button className="rounded border border-line px-2 py-0.5 hover:bg-sunk" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="flex-1 overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="relative mx-auto bg-panel" style={{ width: `${zoom * 100}%`, maxWidth: zoom === 1 ? 1400 : undefined }}>
          <img src={src} alt="" className="block w-full select-none" draggable={false} />
          {overlay && <div className="absolute inset-0">{overlay}</div>}
        </div>
      </div>
    </div>,
    document.body,
  );
}
