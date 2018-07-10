// Copyright 2018 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// @ts-check
'use strict';

/**
 * @fileoverview
 * UI classes and methods for the info cards that display informations about
 * symbols as the user hovers or focuses on them.
 */

{
  const _CANVAS_RADIUS = 40;

  class Infocard {
    constructor(id) {
      this._infocard = document.getElementById(id);
      /** @type {HTMLHeadingElement} */
      this._sizeInfo = this._infocard.querySelector('.size-info');
      /** @type {HTMLParagraphElement} */
      this._pathInfo = this._infocard.querySelector('.path-info');
      /** @type {HTMLDivElement} */
      this._iconInfo = this._infocard.querySelector('.icon-info');
      /** @type {HTMLParagraphElement} */
      this._typeInfo = this._infocard.querySelector('.type-info');

      /**
       * Last symbol type displayed.
       * Tracked to avoid re-cloning the same icon.
       */
      this._lastType = '';
    }

    /**
     * Updates the size header, which normally displayed the byte size of the
     * node followed by an abbreviated version.
     *
     * Example: "1,234 bytes (1.23 KiB)"
     * @param {TreeNode} node
     * @param {GetSize} getSizeLabel
     */
    _updateSize(node, getSizeLabel) {
      const {title, element} = getSizeLabel(
        node.size,
        state.get('byteunit', {default: 'MiB', valid: _BYTE_UNITS_SET})
      );
      const sizeFragment = dom.createFragment([
        document.createTextNode(`${title} (`),
        element,
        document.createTextNode(')'),
      ]);

      // Update DOM
      if (node.size < 0) {
        this._sizeInfo.classList.add('negative');
      } else {
        this._sizeInfo.classList.remove('negative');
      }

      dom.replace(this._sizeInfo, sizeFragment);
    }

    /**
     * Updates the path text, which shows the idPath of the node but highlights
     * the symbol name portion using bold text.
     * @param {TreeNode} node
     */
    _updatePath(node) {
      const path = node.idPath.slice(0, node.shortNameIndex);
      const boldShortName = dom.textElement(
        'span',
        shortName(node),
        'symbol-name-info'
      );
      const pathFragment = dom.createFragment([
        document.createTextNode(path),
        boldShortName,
      ]);

      // Update DOM
      dom.replace(this._pathInfo, pathFragment);
    }

    /**
     * Updates the icon and type text. The type label is pulled from the
     * title of the icon supplied.
     * @param {SVGSVGElement} icon Icon to display
     */
    _setTypeContent(icon) {
      const typeDescription = icon.querySelector('title').textContent;
      icon.setAttribute('fill', '#fff');

      this._typeInfo.textContent = typeDescription;
      this._iconInfo.removeChild(this._iconInfo.lastElementChild);
      this._iconInfo.appendChild(icon);
    }

    /**
     * Toggle wheter or not the card is visible.
     * @param {boolean} isHidden
     */
    setHidden(isHidden) {
      if (isHidden) {
        this._infocard.setAttribute('hidden', '');
      } else {
        this._infocard.removeAttribute('hidden');
      }
    }

    /**
     * Updates the DOM for the info card.
     * @param {TreeNode} node
     * @param {GetSize} getSizeLabel
     */
    _updateInfocard(node, getSizeLabel) {
      const type = node.type[0];

      // Update DOM
      this._updateSize(node, getSizeLabel);
      this._updatePath(node);
      if (type !== this._lastType) {
        // No need to create a new icon if it is identical.
        const icon = getIconTemplate(type);
        this._setTypeContent(icon);
        this._lastType = type;
      }
    }

    /**
     * Updates the card on the next animation frame.
     * @param {TreeNode} node
     * @param {GetSize} getSizeLabel
     */
    updateInfocard(node, getSizeLabel) {
      cancelAnimationFrame(Infocard._pendingFrame);
      Infocard._pendingFrame = requestAnimationFrame(() =>
        this._updateInfocard(node, getSizeLabel)
      );
    }
  }

  class SymbolInfocard extends Infocard {
    /**
     * @param {SVGSVGElement} icon Icon to display
     */
    _setTypeContent(icon) {
      const color = icon.getAttribute('fill');
      super._setTypeContent(icon);
      this._iconInfo.style.backgroundColor = color;
    }
  }

  class ContainerInfocard extends Infocard {
    constructor(id) {
      super(id);
      this._tableBody = this._infocard.querySelector('tbody');
      this._ctx = this._infocard.querySelector('canvas').getContext('2d');

      /**
       * @type {{[type:string]: HTMLTableRowElement}} Rows in the container
       * infocard that represent a particular symbol type.
       */
      this._infoRows = {
        b: this._tableBody.querySelector('.bss-info'),
        d: this._tableBody.querySelector('.data-info'),
        r: this._tableBody.querySelector('.rodata-info'),
        t: this._tableBody.querySelector('.text-info'),
        v: this._tableBody.querySelector('.vtable-info'),
        '*': this._tableBody.querySelector('.gen-info'),
        x: this._tableBody.querySelector('.dexnon-info'),
        m: this._tableBody.querySelector('.dex-info'),
        p: this._tableBody.querySelector('.pak-info'),
        P: this._tableBody.querySelector('.paknon-info'),
        o: this._tableBody.querySelector('.other-info'),
      };

      /**
       * Update the DPI of the canvas for zoomed in and high density screens.
       */
      const _updateCanvasDpi = () => {
        this._ctx.canvas.height = _CANVAS_RADIUS * 2 * devicePixelRatio;
        this._ctx.canvas.width = _CANVAS_RADIUS * 2 * devicePixelRatio;
        this._ctx.scale(devicePixelRatio, devicePixelRatio);
      };

      _updateCanvasDpi();
      window.addEventListener('resize', _updateCanvasDpi);
    }

    /**
     * @param {SVGSVGElement} icon Icon to display
     */
    _setTypeContent(icon) {
      super._setTypeContent(icon);
      icon.classList.add('canvas-overlay');
    }

    /**
     * Draw a slice of a pie chart.
     * @param {number} angleStart Starting angle, in radians.
     * @param {number} percentage Percentage of circle to draw.
     * @param {string} color Color of the pie slice.
     * @returns {number} Ending angle, in radians.
     */
    _drawSlice(angleStart, percentage, color) {
      const arcLength = percentage * 2 * Math.PI;
      const angleEnd = angleStart + arcLength;
      if (arcLength === 0) return angleEnd;

      // Update DOM
      this._ctx.fillStyle = color;
      // Move cursor to center, where line will start
      this._ctx.beginPath();
      this._ctx.moveTo(40, 40);
      // Move cursor to start of arc then draw arc
      this._ctx.arc(40, 40, _CANVAS_RADIUS, angleStart, angleEnd);
      // Move cursor back to center
      this._ctx.closePath();
      this._ctx.fill();

      return angleEnd;
    }

    /**
     * Update a row in the breakdown table with the given values.
     * @param {HTMLTableRowElement} row
     * @param {number} size Total size of the symbols of a given type in a
     * container.
     * @param {number} percentage How much the size represents in relation to
     * the total size of the symbols in the container.
     */
    _updateBreakdownRow(row, size, percentage) {
      if (size === 0) {
        if (row.parentElement != null) {
          this._tableBody.removeChild(row);
        }
        return;
      }

      const sizeColumn = row.querySelector('.size');
      const percentColumn = row.querySelector('.percent');

      const sizeString = size.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
        useGrouping: true,
      });
      const percentString = percentage.toLocaleString(undefined, {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

      // Update DOM
      sizeColumn.textContent = sizeString;
      percentColumn.textContent = percentString;
      this._tableBody.appendChild(row);
    }

    /**
     * Update DOM for the container infocard
     * @param {TreeNode} containerNode
     * @param {GetSize} getSizeLabel
     */
    _updateInfocard(containerNode, getSizeLabel) {
      const extraRows = {...this._infoRows};
      const sizeEntries = Object.entries(containerNode.childSizes).sort(
        (a, b) => b[1] - a[1]
      );

      // Update DOM
      super._updateInfocard(containerNode, getSizeLabel);
      let angleStart = 0;
      for (const [type, size] of sizeEntries) {
        delete extraRows[type];
        const {color} = getIconStyle(type);
        const percentage = size / containerNode.size;

        angleStart = this._drawSlice(angleStart, percentage, color);
        this._updateBreakdownRow(this._infoRows[type], size, percentage);
      }

      // Hide unused types
      for (const row of Object.values(extraRows)) {
        this._updateBreakdownRow(row, 0, 0);
      }
    }
  }

  const _containerInfo = new ContainerInfocard('infocard-container');
  const _symbolInfo = new SymbolInfocard('infocard-symbol');

  /**
   * Displays an infocard for the given symbol on the next frame.
   * @param {TreeNode} node
   * @param {GetSize} getSizeLabel
   */
  function displayInfocard(node, getSizeLabel) {
    if (_CONTAINER_TYPE_SET.has(node.type[0])) {
      _containerInfo.updateInfocard(node, getSizeLabel);
      _containerInfo.setHidden(false);
      _symbolInfo.setHidden(true);
    } else {
      _symbolInfo.updateInfocard(node, getSizeLabel);
      _symbolInfo.setHidden(false);
      _containerInfo.setHidden(true);
    }
  }

  self.displayInfocard = displayInfocard;
}
