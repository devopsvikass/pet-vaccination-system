import {
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
  validatePhoneNumberLength,
} from "libphonenumber-js";

const countryNames = new Intl.DisplayNames(["en"], { type: "region" });

function countryFlag(countryCode) {
  return countryCode
    .toUpperCase()
    .replace(/./g, (letter) => String.fromCodePoint(letter.charCodeAt(0) + 127397));
}

export const countries = getCountries()
  .map((country) => ({
    code: country,
    flag: countryFlag(country),
    name: countryNames.of(country) || country,
    callingCode: getCountryCallingCode(country),
  }))
  .sort((first, second) => first.name.localeCompare(second.name));

export function parseSelectedPhone(phone, country) {
  return parsePhoneNumberFromString(phone || "", country);
}

export function phoneLengthError(phone, country) {
  const result = validatePhoneNumberLength(phone || "", country);
  if (result === "TOO_SHORT") {
    return "Phone number is too short for the selected country.";
  }
  if (result === "TOO_LONG") {
    return "Phone number is too long for the selected country.";
  }
  if (result === "INVALID_LENGTH") {
    return "Phone number length is not valid for the selected country.";
  }
  return "";
}