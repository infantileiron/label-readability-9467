/** @typedef {{visitor_code: string, reading_order: 'old_first'|'new_first', old_ok: boolean|null, new_ok: boolean|null}} ReadingPair */
/** @typedef {{id: number, code: string, title: string, exhibit: string, body: string, type_pt: number, line_height: number}} LabelVersion */
/** @typedef {{id: number, revision: number, status: 'queued'|'succeeded'|'failed', decision: 'publish'|'revise'|null, checksum: string}} ProofRun */
export const completePair = ({ old_ok, new_ok }) => old_ok !== null && new_ok !== null;
