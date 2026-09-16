import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export default function SchematicZoomSvg({ ariaLabel, className, children, controlsHostId = "", height = 340, width = 640 }) {
  const svgRef = useRef(null);
  const panRef = useRef(null);
  const [isPanning, setIsPanning] = useState(false);
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, width, height });
  const [controlsHost, setControlsHost] = useState(null);
  const zoomPercent = Math.round((width / viewBox.width) * 100);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return undefined;

    const handleWheel = (event) => {
      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return;

      const cursorX = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const cursorY = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));

      setViewBox((current) => {
        const factor = event.deltaY < 0 ? 0.88 : 1.14;
        const minWidth = width / 6;
        const maxWidth = width / 0.5;
        const nextWidth = Math.max(minWidth, Math.min(maxWidth, current.width * factor));
        const nextHeight = nextWidth * (height / width);
        const pointerX = current.x + cursorX * current.width;
        const pointerY = current.y + cursorY * current.height;

        return {
          x: pointerX - cursorX * nextWidth,
          y: pointerY - cursorY * nextHeight,
          width: nextWidth,
          height: nextHeight,
        };
      });
    };

    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, [height, width]);

  useEffect(() => {
    if (!controlsHostId || typeof document === "undefined") {
      setControlsHost(null);
      return;
    }
    setControlsHost(document.getElementById(controlsHostId));
  }, [controlsHostId]);

  const handlePointerDown = (event) => {
    if (event.button !== 2) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    event.preventDefault();
    svg.setPointerCapture?.(event.pointerId);
    panRef.current = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      startX: viewBox.x,
      startY: viewBox.y,
      scaleX: viewBox.width / rect.width,
      scaleY: viewBox.height / rect.height,
    };
    setIsPanning(true);
  };

  const handlePointerMove = (event) => {
    const pan = panRef.current;
    if (!pan || pan.pointerId !== event.pointerId) return;
    event.preventDefault();
    const dx = (event.clientX - pan.clientX) * pan.scaleX;
    const dy = (event.clientY - pan.clientY) * pan.scaleY;
    setViewBox((current) => ({ ...current, x: pan.startX - dx, y: pan.startY - dy }));
  };

  const finishPan = (event) => {
    const pan = panRef.current;
    if (!pan || pan.pointerId !== event.pointerId) return;
    panRef.current = null;
    setIsPanning(false);
    svgRef.current?.releasePointerCapture?.(event.pointerId);
  };

  const preventContextMenu = (event) => event.preventDefault();

  const resetView = () => setViewBox({ x: 0, y: 0, width, height });

  return (
    <>
      {controlsHost ? createPortal(
        <div className="mounting-node-schematic-zoom-controls">
          <span className="mounting-node-schematic-zoom-percent">{zoomPercent}%</span>
          <button className="mounting-node-schematic-zoom-reset" onClick={resetView} type="button">Вписати</button>
        </div>,
        controlsHost,
      ) : null}
      <svg
        aria-label={ariaLabel}
        className={className}
        onContextMenu={preventContextMenu}
        onPointerCancel={finishPan}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPan}
        ref={svgRef}
        role="img"
        style={{ cursor: isPanning ? "grabbing" : "grab" }}
        viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`}
      >
        {children}
      </svg>
    </>
  );
}
