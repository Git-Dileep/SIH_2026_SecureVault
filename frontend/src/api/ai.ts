import type { AccuracyReport, FragmentClassification } from '../types';
import { apiGet, apiPost, apiUpload } from './client';

const mockClassification: FragmentClassification = {
  file_type: 'jpg',
  display_type: 'JPEG',
  confidence: 0.94,
  entropy: 7.31,
  scores: {
    jpg: 0.94, png: 0.02, pdf: 0.01, zip: 0.01, docx: 0.0,
    xlsx: 0.0, mp4: 0.01, mp3: 0.01, txt: 0.0, exe: 0.0,
  },
  method: 'mlp+heuristic',
  below_threshold: false,
  features: { printable_ratio: 0.12, zero_ratio: 0.01, magic_flags: { jpg: 1 } },
};

const mockAccuracy: AccuracyReport = {
  model: 'FragmentMLP-3layer (histogram + entropy + magic flags)',
  accuracy: 0.8815,
  threshold: 0.7,
  types: ['jpg', 'png', 'pdf', 'zip', 'docx', 'xlsx', 'mp4', 'mp3', 'txt', 'exe'],
  fragment_size: 512,
  dataset: 'synthetic FFT-75-style 512-byte fragments',
  per_class: {
    jpg: 0.96, png: 0.95, pdf: 0.97, zip: 0.91, docx: 0.93,
    xlsx: 0.92, mp4: 0.94, mp3: 0.9, txt: 0.98, exe: 0.89,
  },
  baseline_signature_only: 0.62,
  notes: 'Transformer/CNN research ceiling is 94–96%. This MLP MVP is trained on synthetic fragments.',
};

export function classifyFragment(input: { file?: File; hex?: string; text?: string }): Promise<FragmentClassification> {
  if (input.file) {
    const form = new FormData();
    form.append('file', input.file);
    return apiUpload('/ai/classify', form, mockClassification);
  }
  return apiPost('/ai/classify', { hex: input.hex, text: input.text }, mockClassification);
}

export function getAccuracy(): Promise<AccuracyReport> {
  return apiGet('/ai/accuracy', mockAccuracy);
}

export function getAccuracyMetrics(): Promise<AccuracyReport> {
  return getAccuracy();
}
