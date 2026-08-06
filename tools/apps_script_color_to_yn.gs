/**
 * Converts a color-coded availability sheet (green = available,
 * red = busy) into a plain Y/N text grid on a separate sheet, ready to
 * export as CSV for the scheduler's parser.
 *
 * SETUP:
 * 1. Open your Google Sheet.
 * 2. Extensions > Apps Script.
 * 3. Delete any placeholder code and paste this whole file in.
 * 4. Update the CONFIG section below to match your actual sheet name,
 *    the range that holds the colored grid, and the header row (names).
 * 5. Save, then run convertColorsToYN from the toolbar (you'll be asked
 *    to authorize it the first time — that's normal, it only touches
 *    this spreadsheet).
 * 6. A new sheet/tab called "Monday_YN" (or whatever you name it) will
 *    be created with the Y/N grid. File > Download > CSV on that tab.
 *
 * Run this once per day-tab (Monday, Tuesday, etc.), updating CONFIG
 * each time, or see the runAllDays() function at the bottom to do all
 * of them in one click if your tabs follow a consistent layout.
 */

const CONFIG = {
  sourceSheetName: "Monday",   // the tab with your colored grid
  outputSheetName: "Monday_YN", // will be created/overwritten
  headerRow: 2,                 // row number containing person names
  firstDataRow: 3,               // first row of actual time-slot data
  firstDataCol: 2,               // first column with a person's colored cells (A=1, B=2, ...)
  timeCol: 1,                    // column containing the time labels (A=1)
};

function convertColorsToYN() {
  convertOneSheet(CONFIG);
}

function convertOneSheet(config) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const source = ss.getSheetByName(config.sourceSheetName);
  if (!source) {
    throw new Error("Sheet not found: " + config.sourceSheetName);
  }

  const lastRow = source.getLastRow();
  const lastCol = source.getLastColumn();

  // Read names from the header row
  const headerRange = source.getRange(config.headerRow, config.firstDataCol, 1, lastCol - config.firstDataCol + 1);
  const names = headerRange.getValues()[0];

  // Read time labels
  const numDataRows = lastRow - config.firstDataRow + 1;
  const timeRange = source.getRange(config.firstDataRow, config.timeCol, numDataRows, 1);
  const times = timeRange.getValues();

  // Read background colors for the whole data grid at once (fast)
  const dataRange = source.getRange(config.firstDataRow, config.firstDataCol, numDataRows, lastCol - config.firstDataCol + 1);
  const colors = dataRange.getBackgrounds();

  // Build output sheet
  let output = ss.getSheetByName(config.outputSheetName);
  if (output) {
    ss.deleteSheet(output);
  }
  output = ss.insertSheet(config.outputSheetName);

  // Write header: "Time" + names
  output.getRange(1, 1, 1, names.length + 1).setValues([["Time", ...names]]);

  // Write each row: time + Y/N per person
  const outputRows = [];
  for (let r = 0; r < numDataRows; r++) {
    const timeValue = times[r][0];
    const rowColors = colors[r];
    const rowResult = rowColors.map(hex => colorToYN(hex));
    outputRows.push([timeValue, ...rowResult]);
  }
  output.getRange(2, 1, outputRows.length, outputRows[0].length).setValues(outputRows);

  // Make time column display as text like "7:30 AM" to match the parser
  output.getRange(2, 1, outputRows.length, 1).setNumberFormat("h:mm AM/PM");

  SpreadsheetApp.getUi().alert("Done! Check the '" + config.outputSheetName + "' tab, then File > Download > CSV.");
}

/**
 * Classifies a background color as "Y" (green/available) or "N"
 * (anything else — red, gray, white/blank, etc.).
 *
 * Adjust the green detection here if your specific shade of green isn't
 * being caught — log a cell's color with Logger.log(hex) to check what
 * hex value your sheet is actually using.
 */
function colorToYN(hex) {
  if (!hex || hex === "#ffffff") return "N";

  const { r, g, b } = hexToRgb(hex);
  // Green cells: green channel clearly dominant over red and blue
  const isGreen = g > r + 15 && g > b + 15;
  return isGreen ? "Y" : "N";
}

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  return {
    r: parseInt(clean.substring(0, 2), 16),
    g: parseInt(clean.substring(2, 4), 16),
    b: parseInt(clean.substring(4, 6), 16),
  };
}

/**
 * Optional: run this instead of convertColorsToYN() to process all five
 * weekday tabs in one click, IF each tab shares the same header row /
 * data row / column layout as CONFIG above. Just update sheetName per
 * day; everything else reuses CONFIG.
 */
function runAllDays() {
  const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
  days.forEach(day => {
    const dayConfig = Object.assign({}, CONFIG, {
      sourceSheetName: day,
      outputSheetName: day + "_YN",
    });
    convertOneSheet(dayConfig);
  });
}