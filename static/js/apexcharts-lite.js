(function () {
  function isObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value);
  }

  function deepMerge(target, source) {
    if (!isObject(source)) return target;
    Object.keys(source).forEach(function (key) {
      var incoming = source[key];
      if (Array.isArray(incoming)) {
        target[key] = incoming.slice();
      } else if (isObject(incoming)) {
        if (!isObject(target[key])) target[key] = {};
        deepMerge(target[key], incoming);
      } else {
        target[key] = incoming;
      }
    });
    return target;
  }

  function esc(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [value];
  }

  function pick(value, index, fallback) {
    if (Array.isArray(value)) return value[index] != null ? value[index] : fallback;
    return value != null ? value : fallback;
  }

  function parsePoint(point) {
    if (Array.isArray(point)) return { x: Number(point[0]), y: Number(point[1]) };
    return { x: Number(point && point.x), y: Number(point && point.y) };
  }

  function normalizeSeries(series) {
    return (series || []).map(function (entry) {
      return {
        name: entry && entry.name ? String(entry.name) : 'Series',
        data: (entry && entry.data ? entry.data : []).map(parsePoint).filter(function (point) {
          return Number.isFinite(point.x) && Number.isFinite(point.y);
        }).sort(function (a, b) {
          return a.x - b.x;
        })
      };
    });
  }

  function flattenSeriesData(series) {
    return (series || []).flatMap(function (entry) {
      return entry.data || [];
    });
  }

  function makeLabelFormatter(axis) {
    var fn = axis && axis.labels && axis.labels.formatter;
    return typeof fn === 'function' ? fn : function (value) {
      return String(Math.round(value * 10) / 10);
    };
  }

  function makeTooltipFormatter(config) {
    var fn = config && config.tooltip && config.tooltip.y && config.tooltip.y.formatter;
    if (typeof fn === 'function') return fn;
    return function (value) {
      return Number.isFinite(Number(value)) ? String(Math.round(Number(value) * 100) / 100) : '—';
    };
  }

  function domainForAxis(axis, series, fallback) {
    var matching = (series || []).filter(function (entry) {
      if (axis && axis.seriesName) return entry.name === axis.seriesName;
      return true;
    });
    var points = flattenSeriesData(matching);
    if (!points.length) {
      return {
        min: axis && Number.isFinite(axis.min) ? Number(axis.min) : fallback.min,
        max: axis && Number.isFinite(axis.max) ? Number(axis.max) : fallback.max,
      };
    }
    var values = points.map(function (point) { return point.y; });
    var min = axis && Number.isFinite(axis.min) ? Number(axis.min) : Math.min.apply(null, values);
    var max = axis && Number.isFinite(axis.max) ? Number(axis.max) : Math.max.apply(null, values);
    if (min === max) {
      min -= 1;
      max += 1;
    }
    return { min: min, max: max };
  }

  function linePath(points, xScale, yScale) {
    if (!points.length) return '';
    return points.map(function (point, index) {
      return (index === 0 ? 'M' : 'L') + ' ' + xScale(point.x).toFixed(2) + ' ' + yScale(point.y).toFixed(2);
    }).join(' ');
  }

  function areaPath(points, xScale, yScale, baseline) {
    if (!points.length) return '';
    var path = 'M ' + xScale(points[0].x).toFixed(2) + ' ' + baseline.toFixed(2);
    points.forEach(function (point) {
      path += ' L ' + xScale(point.x).toFixed(2) + ' ' + yScale(point.y).toFixed(2);
    });
    path += ' L ' + xScale(points[points.length - 1].x).toFixed(2) + ' ' + baseline.toFixed(2) + ' Z';
    return path;
  }

  function formatTimeLabel(ms) {
    var date = new Date(ms);
    return String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0');
  }

  function nearestPoint(points, targetX) {
    if (!points || !points.length) return null;
    var best = points[0];
    var bestDiff = Math.abs(points[0].x - targetX);
    for (var i = 1; i < points.length; i += 1) {
      var diff = Math.abs(points[i].x - targetX);
      if (diff < bestDiff) {
        best = points[i];
        bestDiff = diff;
      }
    }
    return best;
  }

  function annotationPointsMarkup(annotations, xScale, yScaleForPoint) {
    return (((annotations || {}).points) || []).map(function (point) {
      if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return '';
      var fill = point.marker && point.marker.fillColor ? point.marker.fillColor : '#276749';
      var labelText = point.label && point.label.text ? String(point.label.text) : '';
      var offsetY = point.label && Number.isFinite(point.label.offsetY) ? point.label.offsetY : -12;
      var x = xScale(point.x);
      var yScale = yScaleForPoint(point);
      var y = yScale(point.y);
      var markerRadius = point.marker && Number.isFinite(point.marker.size) ? Number(point.marker.size) : 4;
      var labelMarkup = '';
      if (labelText) {
        labelMarkup = '<g transform="translate(' + (x + 8).toFixed(2) + ' ' + (y + offsetY).toFixed(2) + ')">' +
          '<rect x="-3" y="-10" rx="6" ry="6" width="' + Math.max(26, (labelText.length * 6.2) + 10).toFixed(2) + '" height="16" fill="rgba(255,255,255,0.96)" stroke="' + esc(fill) + '" stroke-width="1"></rect>' +
          '<text x="4" y="1" font-size="10" fill="' + esc(fill) + '" font-weight="700">' + esc(labelText) + '</text>' +
          '</g>';
      }
      return '<circle cx="' + x.toFixed(2) + '" cy="' + y.toFixed(2) + '" r="' + markerRadius + '" fill="' + esc(fill) + '" stroke="#fff" stroke-width="1.2"></circle>' + labelMarkup;
    }).join('');
  }

  function yAxisMarkup(annotations, x1, x2, yScale) {
    return (((annotations || {}).yaxis) || []).map(function (row) {
      if (!Number.isFinite(row.y)) return '';
      var y = yScale(row.y);
      var color = row.borderColor || '#0f172a';
      var dash = row.strokeDashArray ? ' stroke-dasharray="' + esc(row.strokeDashArray) + '"' : '';
      var label = row.label && row.label.text
        ? '<g transform="translate(' + (x2 - 6).toFixed(2) + ' ' + (y - 10).toFixed(2) + ')"><rect x="-' + Math.max(18, (String(row.label.text).length * 6.4) + 8).toFixed(2) + '" y="0" width="' + Math.max(18, (String(row.label.text).length * 6.4) + 8).toFixed(2) + '" height="14" rx="6" fill="rgba(255,255,255,0.96)" stroke="' + esc(color) + '" stroke-width="1"></rect><text x="-6" y="10" text-anchor="end" font-size="10" fill="' + esc(color) + '" font-weight="700">' + esc(row.label.text) + '</text></g>'
        : '';
      return '<line x1="' + x1.toFixed(2) + '" y1="' + y.toFixed(2) + '" x2="' + x2.toFixed(2) + '" y2="' + y.toFixed(2) + '" stroke="' + esc(color) + '" stroke-width="1.2"' + dash + '></line>' + label;
    }).join('');
  }

  function xAxisMarkup(annotations, y1, y2, xScale) {
    return (((annotations || {}).xaxis) || []).map(function (row) {
      if (!Number.isFinite(row.x)) return '';
      if (Number.isFinite(row.x2)) {
        var bandLeft = xScale(row.x);
        var bandRight = xScale(row.x2);
        var bandFill = row.fillColor || '#c36a1f';
        var bandOpacity = Number.isFinite(row.opacity) ? Number(row.opacity) : 0.08;
        var bandLabel = row.label && row.label.text
          ? '<g transform="translate(' + ((bandLeft + bandRight) / 2).toFixed(2) + ' ' + (y1 + 8).toFixed(2) + ')"><rect x="-' + Math.max(24, (String(row.label.text).length * 3.3) + 10).toFixed(2) + '" y="0" width="' + Math.max(24, (String(row.label.text).length * 6.4) + 14).toFixed(2) + '" height="16" rx="8" fill="' + esc((row.label && row.label.background) || 'rgba(255,255,255,0.88)') + '" stroke="' + esc((row.label && row.label.color) || bandFill) + '" stroke-width="0.8"></rect><text x="0" y="11" text-anchor="middle" font-size="10" fill="' + esc((row.label && row.label.color) || bandFill) + '" font-weight="700">' + esc(row.label.text) + '</text></g>'
          : '';
        return '<rect x="' + bandLeft.toFixed(2) + '" y="' + y1.toFixed(2) + '" width="' + Math.max(0, bandRight - bandLeft).toFixed(2) + '" height="' + (y2 - y1).toFixed(2) + '" fill="' + esc(bandFill) + '" fill-opacity="' + bandOpacity + '"></rect>' + bandLabel;
      }
      var x = xScale(row.x);
      var color = row.borderColor || '#0891b2';
      var dash = row.strokeDashArray ? ' stroke-dasharray="' + esc(row.strokeDashArray) + '"' : '';
      var label = row.label && row.label.text
        ? '<g transform="translate(' + (x + 8).toFixed(2) + ' ' + (y1 + 8).toFixed(2) + ')"><rect x="0" y="0" width="' + Math.max(24, (String(row.label.text).length * 6.3) + 12).toFixed(2) + '" height="16" rx="8" fill="' + esc((row.label && row.label.background) || 'rgba(255,255,255,0.9)') + '" stroke="' + esc(color) + '" stroke-width="0.9"></rect><text x="6" y="11" font-size="10" fill="' + esc((row.label && row.label.color) || color) + '" font-weight="700">' + esc(row.label.text) + '</text></g>'
        : '';
      return '<line x1="' + x.toFixed(2) + '" y1="' + y1.toFixed(2) + '" x2="' + x.toFixed(2) + '" y2="' + y2.toFixed(2) + '" stroke="' + esc(color) + '" stroke-width="1.2"' + dash + '></line>' + label;
    }).join('');
  }

  function ApexCharts(el, config) {
    this.el = el;
    this.config = deepMerge({}, config || {});
    this._hoverBound = false;
    this._state = null;
  }

  ApexCharts.prototype.render = function () {
    this._render();
    return Promise.resolve();
  };

  ApexCharts.prototype.updateSeries = function (series) {
    this.config.series = Array.isArray(series) ? series.slice() : [];
    this._render();
  };

  ApexCharts.prototype.updateOptions = function (options) {
    deepMerge(this.config, options || {});
    this._render();
  };

  ApexCharts.prototype._ensureDom = function () {
    if (!this.el) return null;
    var root = this.el.querySelector('.apx-root');
    if (root) return root;
    this.el.innerHTML = '<div class="apx-root"><div class="apx-surface"></div><div class="apx-tooltip"></div><div class="apx-legend"></div></div>';
    return this.el.querySelector('.apx-root');
  };

  ApexCharts.prototype._render = function () {
    if (!this.el) return;

    var root = this._ensureDom();
    var surface = root.querySelector('.apx-surface');
    var tooltip = root.querySelector('.apx-tooltip');
    var legendEl = root.querySelector('.apx-legend');
    var width = this.el.clientWidth || 920;
    var height = this.el.clientHeight || 240;
    surface.style.height = height + 'px';

    var margin = { top: 18, right: 58, bottom: 32, left: 56 };
    var plotWidth = Math.max(120, width - margin.left - margin.right);
    var plotHeight = Math.max(96, height - margin.top - margin.bottom);
    var series = normalizeSeries(this.config.series || []);
    var colors = this.config.colors || [];
    var xaxis = this.config.xaxis || {};
    var yAxes = Array.isArray(this.config.yaxis) ? this.config.yaxis : [this.config.yaxis || {}];
    var allPoints = flattenSeriesData(series);
    var fallbackXMin = allPoints.length ? Math.min.apply(null, allPoints.map(function (point) { return point.x; })) : Date.now() - 3600000;
    var fallbackXMax = allPoints.length ? Math.max.apply(null, allPoints.map(function (point) { return point.x; })) : Date.now();
    var xMin = Number.isFinite(xaxis.min) ? Number(xaxis.min) : fallbackXMin;
    var xMax = Number.isFinite(xaxis.max) ? Number(xaxis.max) : Math.max(fallbackXMax, xMin + 1);
    var leftAxisCfg = yAxes.find(function (axis) { return !axis || !axis.opposite; }) || yAxes[0] || {};
    var rightAxisCfg = yAxes.find(function (axis) { return axis && axis.opposite; }) || null;
    var leftDomain = domainForAxis(leftAxisCfg, series, { min: 0, max: 1 });
    var rightDomain = rightAxisCfg ? domainForAxis(rightAxisCfg, series, leftDomain) : leftDomain;

    var xScale = function (value) {
      return margin.left + ((value - xMin) / Math.max(1, xMax - xMin)) * plotWidth;
    };
    var xInvert = function (px) {
      return xMin + ((px - margin.left) / Math.max(1, plotWidth)) * (xMax - xMin);
    };
    var yScaleLeft = function (value) {
      return margin.top + (1 - ((value - leftDomain.min) / Math.max(0.0001, leftDomain.max - leftDomain.min))) * plotHeight;
    };
    var yScaleRight = function (value) {
      return margin.top + (1 - ((value - rightDomain.min) / Math.max(0.0001, rightDomain.max - rightDomain.min))) * plotHeight;
    };
    var yScaleForPoint = function (point) {
      var axisCfg = yAxes.find(function (axis) {
        return axis && axis.seriesName === point.seriesName;
      }) || leftAxisCfg;
      return axisCfg && axisCfg.opposite ? yScaleRight : yScaleLeft;
    };

    var leftFormatter = makeLabelFormatter(leftAxisCfg);
    var rightFormatter = makeLabelFormatter(rightAxisCfg || leftAxisCfg);
    var tooltipFormatter = makeTooltipFormatter(this.config);
    var tickAmount = Number.isFinite(Number(xaxis.tickAmount)) ? Number(xaxis.tickAmount) : 6;
    var svg = '';
    var defs = [
      '<defs>',
      '<linearGradient id="apx-bg" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#fbfefd"></stop><stop offset="100%" stop-color="#eef7f3"></stop></linearGradient>',
      '<clipPath id="apx-clip"><rect x="' + margin.left.toFixed(2) + '" y="' + margin.top.toFixed(2) + '" width="' + plotWidth.toFixed(2) + '" height="' + plotHeight.toFixed(2) + '" rx="10"></rect></clipPath>'
    ];
    series.forEach(function (entry, index) {
      var opacity = Number(pick((this.config.fill || {}).opacity, index, 0) || 0);
      defs.push('<linearGradient id="apx-series-' + index + '" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="' + esc(colors[index] || '#276749') + '" stop-opacity="' + Math.min(0.42, opacity + 0.06) + '"></stop><stop offset="100%" stop-color="' + esc(colors[index] || '#276749') + '" stop-opacity="0"></stop></linearGradient>');
    }, this);
    defs.push('</defs>');

    var gridMarkup = '<rect x="0" y="0" width="' + width + '" height="' + height + '" fill="url(#apx-bg)"></rect>';
    for (var i = 0; i <= 5; i += 1) {
      var fracY = i / 5;
      var y = margin.top + fracY * plotHeight;
      var leftValue = leftDomain.max - fracY * (leftDomain.max - leftDomain.min);
      var rightValue = rightDomain.max - fracY * (rightDomain.max - rightDomain.min);
      gridMarkup += '<line x1="' + margin.left.toFixed(2) + '" y1="' + y.toFixed(2) + '" x2="' + (width - margin.right).toFixed(2) + '" y2="' + y.toFixed(2) + '" stroke="#d7e6dd" stroke-width="1"></line>';
      gridMarkup += '<text x="' + (margin.left - 10).toFixed(2) + '" y="' + (y + 4).toFixed(2) + '" text-anchor="end" font-size="10" fill="#688078">' + esc(leftFormatter(leftValue)) + '</text>';
      if (rightAxisCfg) {
        gridMarkup += '<text x="' + (width - margin.right + 10).toFixed(2) + '" y="' + (y + 4).toFixed(2) + '" text-anchor="start" font-size="10" fill="#688078">' + esc(rightFormatter(rightValue)) + '</text>';
      }
    }
    for (var j = 0; j <= tickAmount; j += 1) {
      var fracX = j / Math.max(1, tickAmount);
      var x = margin.left + fracX * plotWidth;
      var t = xMin + fracX * (xMax - xMin);
      gridMarkup += '<line x1="' + x.toFixed(2) + '" y1="' + margin.top.toFixed(2) + '" x2="' + x.toFixed(2) + '" y2="' + (margin.top + plotHeight).toFixed(2) + '" stroke="#edf4f0" stroke-width="1"></line>';
      gridMarkup += '<text x="' + x.toFixed(2) + '" y="' + (height - 10).toFixed(2) + '" text-anchor="middle" font-size="10" fill="#688078">' + esc(formatTimeLabel(t)) + '</text>';
    }
    if (leftDomain.min <= 0 && leftDomain.max >= 0) {
      var zeroY = yScaleLeft(0);
      gridMarkup += '<line x1="' + margin.left.toFixed(2) + '" y1="' + zeroY.toFixed(2) + '" x2="' + (width - margin.right).toFixed(2) + '" y2="' + zeroY.toFixed(2) + '" stroke="#0f172a" stroke-width="1.4" stroke-opacity="0.75"></line>';
    }

    var annotations = this.config.annotations || {};
    var xAnnotations = xAxisMarkup(annotations, margin.top, margin.top + plotHeight, xScale);
    var yAnnotations = yAxisMarkup(annotations, margin.left, width - margin.right, yScaleLeft);

    var seriesMarkup = '';
    var hoverDots = '';
    var preparedSeries = [];
    series.forEach(function (entry, index) {
      var color = colors[index] || '#276749';
      var axisCfg = yAxes.find(function (axis) { return axis && axis.seriesName === entry.name; }) || leftAxisCfg;
      var yScale = axisCfg && axisCfg.opposite ? yScaleRight : yScaleLeft;
      var widthValue = Number(pick((this.config.stroke || {}).width, index, 2.1) || 2.1);
      var dashArray = pick((this.config.stroke || {}).dashArray, index, 0) || 0;
      var opacity = Number(pick((this.config.fill || {}).opacity, index, 0) || 0);
      var fillType = pick((this.config.fill || {}).type, index, 'solid');
      var path = linePath(entry.data, xScale, yScale);
      if (!path) return;
      var baseline = margin.top + plotHeight;
      if (opacity > 0 && fillType !== 'none') {
        var area = areaPath(entry.data, xScale, yScale, baseline);
        if (area) {
          seriesMarkup += '<path d="' + esc(area) + '" fill="url(#apx-series-' + index + ')" stroke="none" clip-path="url(#apx-clip)"></path>';
        }
      }
      seriesMarkup += '<path d="' + esc(path) + '" fill="none" stroke="' + esc(color) + '" stroke-width="' + widthValue + '" ' + (dashArray ? 'stroke-dasharray="' + esc(dashArray) + '" ' : '') + 'stroke-linecap="round" stroke-linejoin="round" clip-path="url(#apx-clip)"></path>';
      hoverDots += '<circle id="apx-hover-dot-' + index + '" cx="0" cy="0" r="4.8" fill="' + esc(color) + '" stroke="#fff" stroke-width="1.4" style="display:none"></circle>';
      preparedSeries.push({ name: entry.name, color: color, data: entry.data, yScale: yScale, seriesIndex: index });
    }, this);

    var pointAnnotations = annotationPointsMarkup({ points: (((annotations || {}).points) || []).map(function (point) {
      return deepMerge({}, point);
    }).map(function (point) {
      return deepMerge(point, { seriesName: point.seriesName || '' });
    }) }, xScale, function (point) {
      var axisCfg = yAxes.find(function (axis) { return axis && axis.seriesName === point.seriesName; });
      return axisCfg && axisCfg.opposite ? yScaleRight : yScaleLeft;
    });

    surface.innerHTML = '<svg viewBox="0 0 ' + width + ' ' + height + '" width="100%" height="100%" preserveAspectRatio="none">' + defs.join('') + xAnnotations + gridMarkup + yAnnotations + seriesMarkup + '<line id="apx-hover-line" x1="0" y1="' + margin.top.toFixed(2) + '" x2="0" y2="' + (margin.top + plotHeight).toFixed(2) + '" stroke="#0f172a" stroke-width="1" stroke-opacity="0.45" stroke-dasharray="3 4" style="display:none"></line>' + hoverDots + pointAnnotations + '</svg>';

    var legendFormatter = this.config.legend && typeof this.config.legend.formatter === 'function' ? this.config.legend.formatter : null;
    legendEl.innerHTML = preparedSeries.map(function (entry) {
      var label = entry.name;
      if (legendFormatter) {
        label = legendFormatter(entry.name, { seriesIndex: entry.seriesIndex, w: { config: { series: series } } });
      }
      return '<span class="apx-legend-item"><span class="apx-legend-swatch" style="background:' + esc(entry.color) + '"></span>' + esc(label) + '</span>';
    }).join('');

    if (!preparedSeries.length) {
      surface.innerHTML = '<div class="apx-empty">No chart data yet</div>';
      tooltip.style.display = 'none';
    }

    this._state = {
      root: root,
      surface: surface,
      tooltip: tooltip,
      width: width,
      height: height,
      margin: margin,
      plotWidth: plotWidth,
      xScale: xScale,
      xInvert: xInvert,
      preparedSeries: preparedSeries,
      tooltipFormatter: tooltipFormatter,
      config: this.config
    };

    this._bindHover();
  };

  ApexCharts.prototype._bindHover = function () {
    if (this._hoverBound || !this._state || !this._state.surface) return;
    var self = this;
    if (window.PointerEvent) {
      this._state.surface.addEventListener('pointermove', function (event) {
        self._handleHover(event);
      });
      this._state.surface.addEventListener('pointerleave', function () {
        self._clearHover();
      });
    } else {
      this._state.surface.addEventListener('mousemove', function (event) {
        self._handleHover(event);
      });
      this._state.surface.addEventListener('mouseleave', function () {
        self._clearHover();
      });
      this._state.surface.addEventListener('touchmove', function (event) {
        if (!event.touches || !event.touches.length) return;
        self._handleHover(event.touches[0]);
      }, { passive: true });
      this._state.surface.addEventListener('touchend', function () {
        self._clearHover();
      }, { passive: true });
    }
    this._hoverBound = true;
  };

  ApexCharts.prototype._handleHover = function (event) {
    if (!this._state || !this._state.preparedSeries.length) return;
    var rect = this._state.surface.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    var x = ((event.clientX - rect.left) / rect.width) * this._state.width;
    var clampedX = Math.max(this._state.margin.left, Math.min(this._state.margin.left + this._state.plotWidth, x));
    var targetX = this._state.xInvert(clampedX);
    var hoverLine = this._state.surface.querySelector('#apx-hover-line');
    var tooltipRows = [];
    var anchor = null;
    this._state.preparedSeries.forEach(function (entry) {
      var point = nearestPoint(entry.data, targetX);
      var dot = this._state.surface.querySelector('#apx-hover-dot-' + entry.seriesIndex);
      if (!point || !dot) return;
      var px = this._state.xScale(point.x);
      var py = entry.yScale(point.y);
      if (!anchor || Math.abs(point.x - targetX) < Math.abs(anchor.x - targetX)) anchor = point;
      dot.setAttribute('cx', px.toFixed(2));
      dot.setAttribute('cy', py.toFixed(2));
      dot.style.display = '';
      tooltipRows.push({
        name: entry.name,
        color: entry.color,
        value: this._state.tooltipFormatter(point.y, { seriesIndex: entry.seriesIndex, w: { config: this.config } })
      });
    }, this);
    if (!anchor || !hoverLine) return;
    var hoverX = this._state.xScale(anchor.x);
    hoverLine.setAttribute('x1', hoverX.toFixed(2));
    hoverLine.setAttribute('x2', hoverX.toFixed(2));
    hoverLine.style.display = '';

    this._state.tooltip.innerHTML = '<div class="apx-tooltip-time">' + esc(formatTimeLabel(anchor.x)) + '</div>' + tooltipRows.map(function (row) {
      return '<div class="apx-tooltip-row"><span class="apx-tooltip-label" style="color:' + esc(row.color) + '">' + esc(row.name) + '</span><span class="apx-tooltip-value">' + esc(row.value) + '</span></div>';
    }).join('');
    this._state.tooltip.style.display = 'block';
    var tipWidth = this._state.tooltip.offsetWidth || 200;
    var tipHeight = this._state.tooltip.offsetHeight || 88;
    var relX = event.clientX - rect.left;
    var relY = event.clientY - rect.top;
    var left = relX + 12;
    var top = relY - tipHeight - 10;
    if ((left + tipWidth + 10) > rect.width) {
      left = relX - tipWidth - 12;
    }
    if (left < 8) left = 8;
    if (top < 8) top = relY + 12;
    if ((top + tipHeight + 8) > rect.height) {
      top = Math.max(8, rect.height - tipHeight - 8);
    }
    this._state.tooltip.style.left = left + 'px';
    this._state.tooltip.style.top = top + 'px';
  };

  ApexCharts.prototype._clearHover = function () {
    if (!this._state || !this._state.surface) return;
    var hoverLine = this._state.surface.querySelector('#apx-hover-line');
    if (hoverLine) hoverLine.style.display = 'none';
    this._state.preparedSeries.forEach(function (entry) {
      var dot = this._state.surface.querySelector('#apx-hover-dot-' + entry.seriesIndex);
      if (dot) dot.style.display = 'none';
    }, this);
    if (this._state.tooltip) this._state.tooltip.style.display = 'none';
  };

  window.ApexCharts = ApexCharts;
})();