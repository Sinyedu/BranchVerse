/** Does the text the user typed look like a web link rather than a local path? */
export const looksLikeUrl = (input: string): boolean => /^\s*(https?:\/\/|github\.com\/)/i.test(input)
