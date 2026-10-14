/**
 * A temporary password for an account an admin creates or resets (design-doc §4, UI-FRM-11): random
 * from the browser's CSPRNG, at least 16 characters or the policy's minimum, whichever is longer,
 * and without look-alike characters (0/O, 1/l/I), since an admin passes it on by hand. The server
 * still checks it against the policy.
 */
const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
const MIN_LENGTH = 16

export function generateTemporaryPassword(policyMinimum = 0): string {
  const length = Math.max(MIN_LENGTH, policyMinimum)
  const picks = new Uint32Array(length)
  crypto.getRandomValues(picks)
  // 2^32 isn't a multiple of the alphabet's size, so the first few letters are a hair likelier; at
  // 56 letters that bias is about one in 77 million per character, far below what matters here.
  return Array.from(picks, (n) => ALPHABET[n % ALPHABET.length]).join('')
}
