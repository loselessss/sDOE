from __future__ import annotations

import streamlit as st


DESIGN_RESPONSE_TABLE_COMPONENT = None
if hasattr(st.components, "v2"):
    DESIGN_RESPONSE_TABLE_COMPONENT = st.components.v2.component(
        "rsm_design_response_table",
        html="""
        <div class="table-shell">
            <table id="rsm-design-table"></table>
        </div>
        """,
        css="""
        :host {
            display: block;
            width: 100%;
            height: 100%;
            font-family: var(--st-font);
            color: var(--st-text-color);
        }
        .table-shell {
            width: 100%;
            height: 100%;
            overflow: auto;
            border: 1px solid var(--st-border-color);
            border-radius: 6px;
            background: var(--st-background-color);
        }
        table {
            border-collapse: separate;
            border-spacing: 0;
            width: max-content;
            min-width: 100%;
            table-layout: fixed;
        }
        th, td {
            height: 34px;
            padding: 0 8px;
            border-right: 1px solid var(--st-border-color);
            border-bottom: 1px solid var(--st-border-color);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-size: 0.86rem;
            letter-spacing: 0;
            text-align: right;
            box-sizing: border-box;
        }
        th {
            height: 48px;
            position: sticky;
            top: 0;
            z-index: 2;
            background: var(--st-secondary-background-color);
            font-weight: 600;
            text-align: center;
            user-select: none;
            overflow: visible;
        }
        th .header-label {
            display: block;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: pre-line;
            line-height: 1.15;
        }
        .column-resizer {
            position: absolute;
            top: 0;
            right: -4px;
            width: 8px;
            height: 100%;
            cursor: col-resize;
            touch-action: none;
            z-index: 4;
        }
        .column-resizer::after {
            content: "";
            position: absolute;
            top: 7px;
            bottom: 7px;
            left: 3px;
            width: 2px;
            background: transparent;
        }
        .column-resizer:hover::after,
        .column-resizer.resizing::after {
            background: var(--st-primary-color);
        }
        th:last-child, td:last-child { border-right: 0; }
        tr:last-child td { border-bottom: 0; }
        tbody tr:hover td {
            background: color-mix(in srgb, var(--st-primary-color) 4%, var(--st-background-color));
        }
        tbody tr.active-row td {
            background: color-mix(in srgb, var(--st-primary-color) 7%, var(--st-background-color));
        }
        td.text-cell { text-align: left; }
        td.response-cell {
            padding: 0;
            background: color-mix(in srgb, var(--st-primary-color) 5%, var(--st-background-color));
        }
        td.active-cell {
            box-shadow: inset 0 0 0 2px var(--st-primary-color);
            position: relative;
            z-index: 1;
        }
        input {
            width: 100%;
            height: 100%;
            box-sizing: border-box;
            border: 0;
            border-radius: 0;
            padding: 0 8px;
            background: transparent;
            color: var(--st-text-color);
            font: inherit;
            text-align: right;
            letter-spacing: 0;
            outline: none;
        }
        input:focus {
            background: var(--st-background-color);
        }
        """,
        js=r"""
        export default function({ parentElement, data, setStateValue }) {
            const table = parentElement.querySelector("#rsm-design-table");
            const columns = data?.columns ?? [];
            const rows = data?.rows ?? [];
            const editableColumns = data?.editable_columns ?? [];
            const integerColumns = new Set(data?.integer_columns ?? []);
            const savedColumnWidths = data?.column_widths ?? {};
            const columnLabels = data?.column_labels ?? {};
            const resizeTitle = data?.resize_title ?? "Resize column";
            table.replaceChildren();

            const defaultColumnWidth = (column) => {
                if (["Run", "Batch", "RunInBatch", "StdOrder"].includes(column)) return 78;
                if (column === "PointType") return 116;
                if (editableColumns.includes(column)) return 112;
                if (String(column).endsWith("_coded")) return 112;
                return 104;
            };

            const clampWidth = (value) => Math.max(64, Math.min(360, Math.round(value)));
            const colgroup = document.createElement("colgroup");
            const columnElements = new Map();
            columns.forEach((column) => {
                const col = document.createElement("col");
                const saved = Number(savedColumnWidths[column]);
                col.style.width = `${clampWidth(Number.isFinite(saved) ? saved : defaultColumnWidth(column))}px`;
                colgroup.appendChild(col);
                columnElements.set(column, col);
            });
            table.appendChild(colgroup);

            const formatValue = (value, column) => {
                if (value === null || value === undefined || value === "") return "";
                if (column === "PointType") return String(value);
                const numeric = Number(value);
                if (!Number.isFinite(numeric)) return String(value);
                if (integerColumns.has(column)) return String(Math.trunc(numeric));
                return numeric.toFixed(4).replace(/\.?0+$/, "");
            };

            const parseCsvLine = (line) => {
                const cells = [];
                let cell = "";
                let quoted = false;
                for (let index = 0; index < line.length; index += 1) {
                    const char = line[index];
                    if (char === '"') {
                        if (quoted && line[index + 1] === '"') {
                            cell += '"';
                            index += 1;
                        } else {
                            quoted = !quoted;
                        }
                    } else if (char === "," && !quoted) {
                        cells.push(cell.trim());
                        cell = "";
                    } else {
                        cell += char;
                    }
                }
                cells.push(cell.trim());
                return cells;
            };

            const parseClipboard = (text) => {
                const parsed = [];
                const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
                for (const rawLine of lines) {
                    if (!rawLine.trim()) break;
                    let cells;
                    if (rawLine.includes("\t")) cells = rawLine.split("\t");
                    else if (rawLine.includes(",")) cells = parseCsvLine(rawLine);
                    else cells = rawLine.trim().split(/\s+/);
                    parsed.push(cells.map((cell) => cell.trim()));
                }
                return parsed;
            };

            const collectValues = () => rows.map((_, rowIndex) => {
                const values = {};
                editableColumns.forEach((column) => {
                    const input = table.querySelector(`input[data-row="${rowIndex}"][data-column="${column}"]`);
                    values[column] = input?.value?.trim() ?? "";
                });
                return values;
            });

            const emitEdit = (rawText, startRow, startColumn) => {
                setStateValue("edit", {
                    values: collectValues(),
                    raw_text: rawText,
                    start_row: startRow,
                    start_column: startColumn,
                    event_id: `${Date.now()}-${Math.random()}`,
                });
            };

            const currentColumnWidths = () => {
                const widths = {};
                columns.forEach((column) => {
                    const col = columnElements.get(column);
                    widths[column] = clampWidth(col?.getBoundingClientRect().width ?? defaultColumnWidth(column));
                });
                return widths;
            };

            const applyColumnWidth = (column, width) => {
                const col = columnElements.get(column);
                if (!col) return;
                col.style.width = `${clampWidth(width)}px`;
            };

            const persistColumnWidths = () => {
                setStateValue("column_widths", currentColumnWidths());
            };

            const markActiveCell = (input) => {
                table.querySelectorAll("td.active-cell").forEach((cell) => cell.classList.remove("active-cell"));
                table.querySelectorAll("tr.active-row").forEach((row) => row.classList.remove("active-row"));
                input.closest("td")?.classList.add("active-cell");
                input.closest("tr")?.classList.add("active-row");
            };

            const focusEditableCell = (rowIndex, columnIndex) => {
                if (rowIndex < 0 || rowIndex >= rows.length) return;
                if (columnIndex < 0 || columnIndex >= editableColumns.length) return;
                const target = table.querySelector(
                    `input[data-row="${rowIndex}"][data-column="${editableColumns[columnIndex]}"]`
                );
                if (target) {
                    target.focus();
                    target.select();
                }
            };

            const header = document.createElement("thead");
            const headerRow = document.createElement("tr");
            columns.forEach((column) => {
                const th = document.createElement("th");
                const label = document.createElement("span");
                label.className = "header-label";
                label.textContent = columnLabels[column] ?? (column === "PointType" ? "Point type" : column);
                th.appendChild(label);

                const resizer = document.createElement("div");
                resizer.className = "column-resizer";
                resizer.title = resizeTitle;
                resizer.addEventListener("pointerdown", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const startX = event.clientX;
                    const startWidth = columnElements.get(column)?.getBoundingClientRect().width ?? defaultColumnWidth(column);
                    resizer.classList.add("resizing");
                    resizer.setPointerCapture(event.pointerId);

                    const onMove = (moveEvent) => {
                        applyColumnWidth(column, startWidth + moveEvent.clientX - startX);
                    };
                    const onUp = (upEvent) => {
                        resizer.releasePointerCapture(upEvent.pointerId);
                        resizer.classList.remove("resizing");
                        resizer.removeEventListener("pointermove", onMove);
                        resizer.removeEventListener("pointerup", onUp);
                        resizer.removeEventListener("pointercancel", onUp);
                        persistColumnWidths();
                    };
                    resizer.addEventListener("pointermove", onMove);
                    resizer.addEventListener("pointerup", onUp);
                    resizer.addEventListener("pointercancel", onUp);
                });
                resizer.addEventListener("dblclick", (event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    const columnIndex = columns.indexOf(column) + 1;
                    const cells = table.querySelectorAll(`th:nth-child(${columnIndex}), td:nth-child(${columnIndex})`);
                    const autoWidth = Math.max(...Array.from(cells).map((cell) => cell.scrollWidth + 20));
                    applyColumnWidth(column, autoWidth);
                    persistColumnWidths();
                });
                th.appendChild(resizer);
                headerRow.appendChild(th);
            });
            header.appendChild(headerRow);
            table.appendChild(header);

            const body = document.createElement("tbody");
            rows.forEach((row, rowIndex) => {
                const tr = document.createElement("tr");
                columns.forEach((column) => {
                    const td = document.createElement("td");
                    if (editableColumns.includes(column)) {
                        td.className = "response-cell";
                        const input = document.createElement("input");
                        input.type = "text";
                        input.inputMode = "decimal";
                        input.autocomplete = "off";
                        input.value = formatValue(row[column], column);
                        input.dataset.row = String(rowIndex);
                        input.dataset.column = column;
                        input.setAttribute("aria-label", `${columnLabels[column] ?? column} Run ${rowIndex + 1}`);
                        input.addEventListener("focus", () => markActiveCell(input));
                        input.addEventListener("keydown", (event) => {
                            const columnIndex = editableColumns.indexOf(column);
                            if (event.key === "Enter") {
                                event.preventDefault();
                                focusEditableCell(rowIndex + (event.shiftKey ? -1 : 1), columnIndex);
                            } else if (event.key === "ArrowUp") {
                                event.preventDefault();
                                focusEditableCell(rowIndex - 1, columnIndex);
                            } else if (event.key === "ArrowDown") {
                                event.preventDefault();
                                focusEditableCell(rowIndex + 1, columnIndex);
                            }
                        });
                        input.addEventListener("change", () => emitEdit("", rowIndex, column));
                        input.addEventListener("paste", (event) => {
                            const text = event.clipboardData?.getData("text/plain") ?? "";
                            event.preventDefault();
                            const pastedRows = parseClipboard(text);
                            const startColumnIndex = editableColumns.indexOf(column);
                            pastedRows.forEach((pastedRow, rowOffset) => {
                                pastedRow.forEach((value, columnOffset) => {
                                    const targetRow = rowIndex + rowOffset;
                                    const targetColumn = editableColumns[startColumnIndex + columnOffset];
                                    if (targetRow >= rows.length || !targetColumn) return;
                                    const target = table.querySelector(
                                        `input[data-row="${targetRow}"][data-column="${targetColumn}"]`
                                    );
                                    if (target) target.value = value;
                                });
                            });
                            emitEdit(text, rowIndex, column);
                        });
                        td.appendChild(input);
                    } else {
                        td.textContent = formatValue(row[column], column);
                        if (column === "PointType") td.className = "text-cell";
                    }
                    tr.appendChild(td);
                });
                body.appendChild(tr);
            });
            table.appendChild(body);
        }
        """,
    )

