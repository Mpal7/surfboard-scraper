// src/utils/formatters.ts

/**
 * Converts a decimal number to its fractional representation.
 * e.g., 21.25 -> "21 ¼"
 */
export const toFraction = (value: number | null): string => {
  if (value === null) return 'N/A';
  const integer = Math.floor(value);
  const decimal = value - integer;
  let fraction = '';

  if (decimal > 0) {
    if (decimal >= 0.9375) fraction = ''; // Almost a whole number, round up implicitly
    else if (decimal >= 0.8125) fraction = '⅞';
    else if (decimal >= 0.6875) fraction = '¾';
    else if (decimal >= 0.5625) fraction = '⅝';
    else if (decimal >= 0.4375) fraction = '½';
    else if (decimal >= 0.3125) fraction = '⅜';
    else if (decimal >= 0.21875) fraction = '¼';
    else if (decimal >= 0.0625) fraction = '⅛';
  }

  const integerPart = integer > 0 ? `${integer}` : '';
  const separator = integerPart && fraction ? ' ' : '';
  
  return `${integerPart}${separator}${fraction}` || '0';
};


/**
 * Formats the length of a surfboard into ft'in" format.
 * e.g., { length_ft: 6, length_in: 2 } -> "6'2\""
 */
export const formatLength = (ft: number | null, inches: number | null): string => {
  if (ft === null) return 'N/A';
  return `${ft}'${inches || 0}"`;
};