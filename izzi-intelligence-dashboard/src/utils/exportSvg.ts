export function downloadSvgAsPng(svgElement: SVGSVGElement, fileName: string): void {
  const serializer = new XMLSerializer();
  const source = serializer.serializeToString(svgElement);
  const svgBlob = new Blob([`<?xml version="1.0" encoding="UTF-8"?>${source}`], {
    type: "image/svg+xml;charset=utf-8",
  });

  const url = URL.createObjectURL(svgBlob);
  const image = new Image();
  const viewBox = svgElement.viewBox.baseVal;
  const width = viewBox?.width || svgElement.clientWidth || 800;
  const height = viewBox?.height || svgElement.clientHeight || 400;

  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      URL.revokeObjectURL(url);
      return;
    }
    context.fillStyle = "#0f172a";
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    URL.revokeObjectURL(url);

    canvas.toBlob((blob) => {
      if (!blob) return;
      const pngUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = pngUrl;
      link.download = fileName.endsWith(".png") ? fileName : `${fileName}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      setTimeout(() => URL.revokeObjectURL(pngUrl), 2000);
    }, "image/png");
  };

  image.onerror = () => {
    URL.revokeObjectURL(url);
  };

  image.src = url;
}
