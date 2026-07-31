/** @odoo-module **/
/**
 * utils.js — Shared helper functions used across Portal components.
 */

/**
 * Format a number as Vietnamese Đồng currency.
 * e.g. 95000 → "95.000đ"
 */
export function formatVND(n) {
    return new Intl.NumberFormat('vi-VN').format(Math.round(n || 0)) + 'đ';
}

/**
 * Calculate percentage (clamped 0–100), safe for zero denominator.
 * e.g. pct(200000, 417000) → 47
 */
export function pct(numerator, denominator) {
    if (!denominator) return 0;
    return Math.min(100, Math.round((numerator / denominator) * 100));
}

/**
 * Generate a deterministic color palette entry for a product/category.
 * Returns [bg, tc] (background color, text color).
 */
const PALETTES = [
    ['#FEF3E8', '#6F3C09'],
    ['#FAECE7', '#712B13'],
    ['#FAEEDA', '#633806'],
    ['#FBEAF0', '#72243E'],
    ['#EAF3DE', '#27500A'],
    ['#E6F1FB', '#0C447C'],
];

export function getPalette(index) {
    return PALETTES[index % PALETTES.length];
}

/**
 * Debounce a function call.
 */
export function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}
