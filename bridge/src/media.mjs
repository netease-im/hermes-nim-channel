import { execFile as execFileCallback } from "node:child_process";
import { access } from "node:fs/promises";
import { constants } from "node:fs";
import { basename } from "node:path";
import { promisify } from "node:util";

const execFile = promisify(execFileCallback);

const MEDIA_KINDS = new Set(["image", "file", "audio", "video"]);

export function normalizeMediaKind(value) {
  const kind = String(value ?? "").trim().toLowerCase();
  if (!MEDIA_KINDS.has(kind)) {
    throw new Error(`unsupported media_kind: ${value ?? ""}`);
  }
  return kind;
}

export function coerceAudioMetadata(probeResult) {
  const durationRaw = Number(probeResult?.format?.duration ?? 0);
  const duration = Math.max(1, Math.round(durationRaw));
  if (!Number.isFinite(durationRaw) || durationRaw <= 0) {
    throw new Error("ffprobe did not return a valid audio duration");
  }
  return { duration };
}

export function coerceVideoMetadata(probeResult) {
  const durationRaw = Number(probeResult?.format?.duration ?? 0);
  const duration = Math.max(1, Math.round(durationRaw));
  const videoStream = (probeResult?.streams ?? []).find(
    (stream) => stream?.codec_type === "video",
  );
  const width = Number(videoStream?.width ?? 0);
  const height = Number(videoStream?.height ?? 0);

  if (!Number.isFinite(durationRaw) || durationRaw <= 0) {
    throw new Error("ffprobe did not return a valid video duration");
  }
  if (!Number.isFinite(width) || width <= 0 || !Number.isFinite(height) || height <= 0) {
    throw new Error("ffprobe did not return valid video dimensions");
  }

  return { duration, width, height };
}

async function probeMedia(filePath) {
  await access(filePath, constants.R_OK);
  const { stdout } = await execFile(
    "ffprobe",
    [
      "-v",
      "error",
      "-show_entries",
      "format=duration:stream=codec_type,width,height",
      "-of",
      "json",
      filePath,
    ],
    {
      timeout: 10000,
      maxBuffer: 1024 * 1024,
    },
  );
  return JSON.parse(stdout);
}

export async function createMediaMessage(messageCreator, kind, filePath) {
  const safeKind = normalizeMediaKind(kind);

  await access(filePath, constants.R_OK);
  const fileName = basename(filePath);

  if (safeKind === "image") {
    return messageCreator?.createImageMessage?.(filePath, fileName) ?? null;
  }

  if (safeKind === "file") {
    return messageCreator?.createFileMessage?.(filePath, fileName) ?? null;
  }

  const probeResult = await probeMedia(filePath);

  if (safeKind === "audio") {
    const meta = coerceAudioMetadata(probeResult);
    return messageCreator?.createAudioMessage?.(filePath, fileName, "", meta.duration) ?? null;
  }

  const meta = coerceVideoMetadata(probeResult);
  return (
    messageCreator?.createVideoMessage?.(
      filePath,
      fileName,
      "",
      meta.duration,
      meta.width,
      meta.height,
    ) ?? null
  );
}
