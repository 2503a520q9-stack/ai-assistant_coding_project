// Leaflet maps: flood monitoring map (flood_map.html) and shelter map with routes (shelters.html)

var RISK_COLORS = { Low: "#2fb36d", Medium: "#f0a500", High: "#e5383b" };

// Escape text before putting it into HTML (reports are typed by the public)
function esc(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
}

function baseMap(elementId, center, zoom) {
    var map = L.map(elementId).setView(center, zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    return map;
}

function iconPin(color, iconClass, size) {
    size = size || 30;
    return L.divIcon({
        className: "",
        html: '<div class="pin" style="background:' + color + ';width:' + size + 'px;height:' + size + 'px"><i class="bi ' + iconClass + '"></i></div>',
        iconSize: [size, size], iconAnchor: [size / 2, size / 2], popupAnchor: [0, -size / 2]
    });
}

function simBadge(item) {
    return item.is_simulated ? ' <span class="sim-tag">Simulated</span>' : "";
}

function locationPopup(l) {
    return "<strong>" + esc(l.name) + "</strong>, " + esc(l.city) + simBadge(l) +
        '<br>Risk: <b style="color:' + RISK_COLORS[l.risk_level] + '">' + esc(l.risk_level) + "</b>" +
        "<br>Rainfall (24 h): " + esc(l.rainfall_mm) + " mm" +
        "<br>River: " + esc(l.river_level_m) + " m (danger " + esc(l.danger_level_m) + " m)" +
        "<br><small>Source: " + esc(l.source) + "<br>Updated: " + esc(l.updated_at) + "</small>";
}

function shelterPopup(s) {
    var free = Math.max(s.capacity - s.occupancy, 0);
    return "<strong>" + esc(s.name) + "</strong>" + simBadge(s) +
        "<br>" + esc(s.address) +
        "<br>Status: <b>" + esc(s.status) + "</b> | Free space: " + free + " of " + esc(s.capacity) +
        "<br><small>Updated: " + esc(s.updated_at) + "</small>";
}

function reportPopup(r) {
    return "<strong>Flood report: " + esc(r.location_name) + "</strong>" + simBadge(r) +
        "<br>Severity: " + esc(r.severity) + " | Depth: " + esc(r.water_depth_cm) + " cm" +
        "<br>" + esc(r.description) +
        "<br><small>Status: " + esc(r.status) + " | " + esc(r.created_at) + "</small>";
}

/* ------------------------------------------------------------------ */
/* Flood monitoring map                                               */
/* ------------------------------------------------------------------ */
function initFloodMap() {
    var map = baseMap("map", [15.5, 79.0], 5);
    var layers = { locations: L.layerGroup().addTo(map), shelters: L.layerGroup().addTo(map), reports: L.layerGroup().addTo(map) };
    var data = { locations: [], shelters: [], reports: [] };
    var markers = {};

    function showDetail(html) { document.getElementById("detail").innerHTML = html; }

    function render() {
        var term = document.getElementById("search").value.trim().toLowerCase();
        var allowed = {};
        ["Low", "Medium", "High"].forEach(function (lv) { allowed[lv] = document.getElementById("f-" + lv.toLowerCase()).checked; });
        var showLoc = document.getElementById("layer-locations").checked;
        var showShe = document.getElementById("layer-shelters").checked;
        var showRep = document.getElementById("layer-reports").checked;
        Object.keys(layers).forEach(function (k) { layers[k].clearLayers(); });
        var list = document.getElementById("result-list");
        list.innerHTML = "";
        var bounds = [];

        if (showLoc) {
            data.locations.forEach(function (l) {
                var text = (l.name + " " + l.city).toLowerCase();
                if (!allowed[l.risk_level] || (term && text.indexOf(term) === -1)) { return; }
                var m = L.circleMarker([l.latitude, l.longitude], {
                    radius: 13, color: "#fff", weight: 2, fillColor: RISK_COLORS[l.risk_level], fillOpacity: 0.9
                }).bindPopup(locationPopup(l)).addTo(layers.locations);
                m.on("click", function () { selectLocation(l); });
                markers["loc" + l.id] = m;
                bounds.push([l.latitude, l.longitude]);
                var li = document.createElement("button");
                li.type = "button";
                li.className = "list-group-item list-group-item-action d-flex justify-content-between align-items-center";
                li.innerHTML = "<span>" + esc(l.name) + "<br><small class='text-muted'>" + esc(l.city) + "</small></span>" +
                    '<span class="badge" style="background:' + RISK_COLORS[l.risk_level] + '">' + esc(l.risk_level) + "</span>";
                li.addEventListener("click", function () { map.flyTo([l.latitude, l.longitude], 11); m.openPopup(); selectLocation(l); });
                list.appendChild(li);
            });
        }
        if (showShe) {
            data.shelters.forEach(function (s) {
                if (term && (s.name + " " + s.city).toLowerCase().indexOf(term) === -1) { return; }
                var color = s.status === "Open" ? "#0b6fa4" : "#6c757d";
                L.marker([s.latitude, s.longitude], { icon: iconPin(color, "bi-house-heart-fill") })
                    .bindPopup(shelterPopup(s)).addTo(layers.shelters);
                bounds.push([s.latitude, s.longitude]);
            });
        }
        if (showRep) {
            data.reports.forEach(function (r) {
                if (term && r.location_name.toLowerCase().indexOf(term) === -1) { return; }
                if (!allowed[r.severity]) { return; }
                L.marker([r.latitude, r.longitude], { icon: iconPin("#ff8a1f", "bi-exclamation-triangle-fill", 26) })
                    .bindPopup(reportPopup(r)).addTo(layers.reports);
                bounds.push([r.latitude, r.longitude]);
            });
        }
        if (!list.children.length) { list.innerHTML = '<div class="p-3 text-muted small">No flood-prone locations match your filters.</div>'; }
        if (term && bounds.length) { map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 }); }
    }

    function selectLocation(l) {
        showDetail(
            "<h6 class='mb-1'>" + esc(l.name) + ", " + esc(l.city) + simBadge(l) + "</h6>" +
            '<span class="badge mb-2" style="background:' + RISK_COLORS[l.risk_level] + '">' + esc(l.risk_level) + " risk</span>" +
            "<ul class='list-unstyled small mb-2'>" +
            "<li><b>Rainfall (24 h):</b> " + esc(l.rainfall_mm) + " mm</li>" +
            "<li><b>River level:</b> " + esc(l.river_level_m) + " m (danger " + esc(l.danger_level_m) + " m)</li>" +
            "<li><b>Notes:</b> " + esc(l.notes) + "</li>" +
            "<li><b>Source:</b> " + esc(l.source) + "</li>" +
            "<li><b>Last updated:</b> " + esc(l.updated_at) + "</li></ul>" +
            '<a class="btn btn-sm btn-navy" href="/shelters?q=' + encodeURIComponent(l.city) + '">Find shelters in ' + esc(l.city) + "</a>");
    }

    fetch("/api/map-data").then(function (r) { return r.json(); }).then(function (d) {
        data = d;
        render();
        var pts = d.locations.map(function (l) { return [l.latitude, l.longitude]; });
        if (pts.length) { map.fitBounds(pts, { padding: [30, 30] }); }
    }).catch(function () {
        document.getElementById("result-list").innerHTML = '<div class="p-3 text-danger small">Could not load map data.</div>';
    });

    ["search", "f-low", "f-medium", "f-high", "layer-locations", "layer-shelters", "layer-reports"].forEach(function (id) {
        document.getElementById(id).addEventListener("input", render);
        document.getElementById(id).addEventListener("change", render);
    });
}

/* ------------------------------------------------------------------ */
/* Shelter map with optional route (OSRM public demo server)          */
/* ------------------------------------------------------------------ */
function initShelterMap() {
    var cards = document.querySelectorAll("[data-shelter]");
    var map = baseMap("shelter-map", [15.5, 79.0], 5);
    var markers = {}, bounds = [], routeLayer = null, startMarker = null, waitingForClick = false;

    cards.forEach(function (card) {
        var lat = parseFloat(card.dataset.lat), lng = parseFloat(card.dataset.lng), id = card.dataset.shelter;
        var open = card.dataset.open === "1";
        var m = L.marker([lat, lng], { icon: iconPin(open ? "#0b6fa4" : "#6c757d", "bi-house-heart-fill") })
            .bindPopup("<strong>" + esc(card.dataset.name) + "</strong><br>" + esc(card.dataset.address)).addTo(map);
        markers[id] = m;
        bounds.push([lat, lng]);
    });
    if (bounds.length) { map.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 }); }

    document.querySelectorAll(".focus-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var card = btn.closest("[data-shelter]");
            map.flyTo([parseFloat(card.dataset.lat), parseFloat(card.dataset.lng)], 14);
            markers[card.dataset.shelter].openPopup();
            document.getElementById("shelter-map").scrollIntoView({ behavior: "smooth", block: "center" });
        });
    });

    var info = document.getElementById("route-info");
    function setInfo(html, cls) { info.className = "alert alert-" + (cls || "warning") + " small"; info.innerHTML = html; info.classList.remove("d-none"); }

    function drawRoute(start, card) {
        var end = [parseFloat(card.dataset.lat), parseFloat(card.dataset.lng)];
        var url = "https://router.project-osrm.org/route/v1/driving/" + start[1] + "," + start[0] + ";" + end[1] + "," + end[0] +
            "?overview=full&geometries=geojson";
        setInfo("Finding a route to " + esc(card.dataset.name) + "...", "info");
        fetch(url).then(function (r) { return r.json(); }).then(function (data) {
            if (!data.routes || !data.routes.length) { setInfo("No road route was found between these points.", "danger"); return; }
            var route = data.routes[0];
            if (routeLayer) { map.removeLayer(routeLayer); }
            routeLayer = L.geoJSON(route.geometry, { style: { color: "#00b8d9", weight: 5 } }).addTo(map);
            map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
            setInfo("<b>Route to " + esc(card.dataset.name) + ":</b> about " + (route.distance / 1000).toFixed(1) + " km, " +
                Math.round(route.duration / 60) + " min by car (normal conditions).<br>" +
                "<b>Warning:</b> this route has NOT been checked against current flood conditions. Roads may be flooded or closed. " +
                "Follow instructions from local authorities.", "warning");
        }).catch(function () {
            setInfo("The routing service could not be reached. Check your internet connection and try again.", "danger");
        });
    }

    document.querySelectorAll(".route-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var card = btn.closest("[data-shelter]");
            document.getElementById("shelter-map").scrollIntoView({ behavior: "smooth", block: "center" });
            function useStart(latlng) {
                if (startMarker) { map.removeLayer(startMarker); }
                startMarker = L.marker(latlng, { icon: iconPin("#e5383b", "bi-geo-alt-fill", 28) }).addTo(map).bindPopup("Your start point");
                drawRoute(latlng, card);
            }
            function askClick() {
                waitingForClick = true;
                setInfo("Could not read your location. <b>Click on the map</b> to choose your starting point.", "warning");
                map.once("click", function (e) { waitingForClick = false; useStart([e.latlng.lat, e.latlng.lng]); });
            }
            if (!navigator.geolocation) { askClick(); return; }
            setInfo("Getting your location...", "info");
            navigator.geolocation.getCurrentPosition(function (pos) {
                useStart([pos.coords.latitude, pos.coords.longitude]);
            }, askClick, { timeout: 8000 });
        });
    });
}

document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById("map")) { initFloodMap(); }
    if (document.getElementById("shelter-map")) { initShelterMap(); }
});
