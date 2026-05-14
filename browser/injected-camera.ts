type FrameStatus = "ok" | "miss";

type FrameMessage = {
  status: FrameStatus;
  imageDataUrl: string;
  capturedAt: string;
  payload?: string;
};

type Options = {
  width: number;
  height: number;
  fps: number;
  zoomMax: number;
  label: string;
  deviceId: string;
};

type GetUserMediaInput = MediaStreamConstraints | boolean;

declare global {
  interface Window {
    __QR_DEBUG_CAMERA_OPTIONS__?: Partial<Options>;
    __qrDebugCameraInstalled?: boolean;
    __qrDebugCameraFrame?: (frame: FrameMessage) => void;
  }
}

const fallbackOptions: Options = {
  width: 1280,
  height: 720,
  fps: 30,
  zoomMax: 0.8,
  label: "QR Debug Camera",
  deviceId: "qr-debug-camera",
};

(() => {
  const options: Options = {
    ...fallbackOptions,
    ...(window.__QR_DEBUG_CAMERA_OPTIONS__ ?? {}),
  };

  if (window.__qrDebugCameraInstalled) {
    return;
  }
  window.__qrDebugCameraInstalled = true;

  const canvas = document.createElement("canvas");
  canvas.width = options.width;
  canvas.height = options.height;
  canvas.style.cssText =
    "position:fixed;left:-10000px;top:-10000px;width:1px;height:1px;pointer-events:none;";
  const mountPoint = document.documentElement ?? document.body;
  mountPoint?.appendChild(canvas);

  const context = canvas.getContext("2d", { alpha: false });
  if (!context) {
    return;
  }
  const ctx = context;
  const stream = canvas.captureStream(options.fps);

  function drawStatus(status: FrameStatus): void {
    const ok = status === "ok";
    ctx.save();
    ctx.font = "bold 112px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "top";
    ctx.fillStyle = ok ? "rgba(0, 190, 110, 0.94)" : "rgba(230, 45, 45, 0.94)";
    ctx.strokeStyle = "rgba(0, 0, 0, 0.55)";
    ctx.lineWidth = 10;
    const mark = ok ? "〇" : "✖";
    ctx.strokeText(mark, canvas.width - 36, 24);
    ctx.fillText(mark, canvas.width - 36, 24);
    ctx.restore();
  }

  function drawEmpty(): void {
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    drawStatus("miss");
  }

  function fit(width: number, height: number, maxWidth: number, maxHeight: number) {
    const ratio = Math.min(maxWidth / width, maxHeight / height);
    const drawWidth = Math.max(1, Math.floor(width * ratio));
    const drawHeight = Math.max(1, Math.floor(height * ratio));
    return {
      x: Math.floor((canvas.width - drawWidth) / 2),
      y: Math.floor((canvas.height - drawHeight) / 2),
      width: drawWidth,
      height: drawHeight,
    };
  }

  async function drawFrame(frame: FrameMessage): Promise<void> {
    const response = await fetch(frame.imageDataUrl);
    const blob = await response.blob();
    const bitmap = await createImageBitmap(blob);

    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const maxRatio = frame.status === "ok" ? options.zoomMax : 1;
    const rect = fit(bitmap.width, bitmap.height, canvas.width * maxRatio, canvas.height * maxRatio);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(bitmap, rect.x, rect.y, rect.width, rect.height);
    drawStatus(frame.status);
  }

  window.__qrDebugCameraFrame = (frame: FrameMessage): void => {
    drawFrame(frame).catch(drawEmpty);
  };

  drawEmpty();

  const mediaDevices = navigator.mediaDevices ?? ({} as MediaDevices);
  const mutableMediaDevices = mediaDevices as MediaDevices & Record<string, unknown>;
  const originalGetUserMedia = mediaDevices.getUserMedia?.bind(mediaDevices);
  const originalEnumerateDevices = mediaDevices.enumerateDevices?.bind(mediaDevices);

  Object.defineProperty(mutableMediaDevices, "getUserMedia", {
    configurable: true,
    value: async (constraints: GetUserMediaInput = {}) => {
      const wantsVideo =
        constraints === true ||
        (typeof constraints === "object" && Boolean(constraints.video));
      if (!wantsVideo && originalGetUserMedia) {
        return originalGetUserMedia(
          typeof constraints === "object" ? constraints : { video: false },
        );
      }

      const result = new MediaStream(stream.getVideoTracks());
      const audio =
        typeof constraints === "object" && constraints ? constraints.audio : false;
      if (audio && originalGetUserMedia) {
        try {
          const audioStream = await originalGetUserMedia({
            audio,
            video: false,
          });
          for (const track of audioStream.getAudioTracks()) {
            result.addTrack(track);
          }
        } catch {
          // Video-only debugging remains useful when microphone permission is unavailable.
        }
      }
      return result;
    },
  });

  Object.defineProperty(mutableMediaDevices, "enumerateDevices", {
    configurable: true,
    value: async () => {
      const devices = originalEnumerateDevices ? await originalEnumerateDevices() : [];
      const fakeDevice = {
        deviceId: options.deviceId,
        groupId: "qr-debug-camera",
        kind: "videoinput",
        label: options.label,
        toJSON() {
          return {
            deviceId: this.deviceId,
            groupId: this.groupId,
            kind: this.kind,
            label: this.label,
          };
        },
      };
      return [fakeDevice, ...devices.filter((device) => device.deviceId !== options.deviceId)];
    },
  });

  if (!navigator.mediaDevices) {
    Object.defineProperty(navigator, "mediaDevices", {
      value: mutableMediaDevices,
      configurable: true,
    });
  }

  if (navigator.permissions?.query) {
    const originalQuery = navigator.permissions.query.bind(navigator.permissions);
    Object.defineProperty(navigator.permissions, "query", {
      configurable: true,
      value: async (descriptor: PermissionDescriptor) => {
        if (descriptor.name === "camera") {
          return {
            state: "granted",
            onchange: null,
            addEventListener() {},
            removeEventListener() {},
            dispatchEvent() {
              return false;
            },
          };
        }
        return originalQuery(descriptor);
      },
    });
  }
})();

export {};
