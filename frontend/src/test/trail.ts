/** The page's breadcrumb trail as a screen reader meets it (DL-327): each link's text and href, then
 * the current crumb's text; null when the page has no trail. */
export function trail(): { links: string[][]; current: string } | null {
  const nav = document.querySelector('nav[aria-label=Breadcrumb]')
  if (!nav) return null
  return {
    links: [...nav.querySelectorAll('a')].map((a) => [
      a.textContent!.trim(),
      a.getAttribute('href')!,
    ]),
    current: nav.querySelector('[aria-current=page]')!.textContent!.trim(),
  }
}
