/** True when built for Vercel (static pre-generated files). False for local API dev. */
export const IS_STATIC = import.meta.env.VITE_STATIC === 'true';
