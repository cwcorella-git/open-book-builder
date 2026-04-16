import { isTauri } from './dataset-source';

export type SaveResult = 'saved' | 'canceled';

/**
 * Persist text to disk across both runtime targets.
 *
 * - Tauri (desktop): opens the native Save dialog via `tauri-plugin-dialog`,
 *   then writes via `tauri-plugin-fs`. Returns `'canceled'` if the user
 *   dismisses the dialog.
 * - Web (static): constructs a Blob, creates an object URL, simulates a
 *   click on a hidden `<a download>`, then revokes the URL. Browsers don't
 *   surface a cancel signal, so this path always returns `'saved'`.
 *
 * The plugin modules are imported lazily so the web build doesn't pull
 * Tauri code into its bundle.
 */
export async function saveTextFile(
  defaultName: string,
  contents: string,
): Promise<SaveResult> {
  if (isTauri()) {
    const { save } = await import('@tauri-apps/plugin-dialog');
    const { writeTextFile } = await import('@tauri-apps/plugin-fs');

    const ext = defaultName.split('.').pop() ?? '';
    const filterName = ext.toUpperCase() || 'File';
    const path = await save({
      defaultPath: defaultName,
      filters: ext ? [{ name: filterName, extensions: [ext] }] : undefined,
    });
    if (path === null || path === undefined) return 'canceled';

    await writeTextFile(path, contents);
    return 'saved';
  }

  // Web path: trigger a browser download via an ephemeral anchor.
  const blob = new Blob([contents], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = defaultName;
  anchor.rel = 'noopener';
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Revoke on the next tick to let the browser start the download first.
  setTimeout(() => URL.revokeObjectURL(url), 0);
  return 'saved';
}
