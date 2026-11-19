// General page behaviour shared by all pages.
document.addEventListener("DOMContentLoaded", function () {
    // Auto-hide flash messages after 8 seconds
    document.querySelectorAll(".alert.auto-dismiss").forEach(function (el) {
        setTimeout(function () {
            if (window.bootstrap) { bootstrap.Alert.getOrCreateInstance(el).close(); }
        }, 8000);
    });

    // Ask for confirmation before dangerous actions: <form data-confirm="Are you sure?">
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            if (!confirm(form.dataset.confirm)) { e.preventDefault(); }
        });
    });

    // "Use my location" button: fills hidden latitude/longitude fields
    var locBtn = document.getElementById("use-location");
    if (locBtn) {
        locBtn.addEventListener("click", function () {
            var note = document.getElementById("location-note");
            if (!navigator.geolocation) { note.textContent = "Your browser does not support location."; return; }
            note.textContent = "Getting your location...";
            navigator.geolocation.getCurrentPosition(function (pos) {
                document.getElementById("latitude").value = pos.coords.latitude.toFixed(6);
                document.getElementById("longitude").value = pos.coords.longitude.toFixed(6);
                note.textContent = "Location added (" + pos.coords.latitude.toFixed(4) + ", " + pos.coords.longitude.toFixed(4) + ").";
            }, function () {
                note.textContent = "Could not get your location. Please type your address instead.";
            }, { timeout: 10000 });
        });
    }

    // Fill the risk-assessment form from a chosen known location
    var locSelect = document.getElementById("location_id");
    if (locSelect) {
        locSelect.addEventListener("change", function () {
            if (!locSelect.value) { return; }
            fetch("/api/location/" + locSelect.value).then(function (r) { return r.json(); }).then(function (d) {
                document.getElementById("rainfall").value = d.rainfall_mm;
                document.getElementById("river_level").value = d.river_level_m;
                document.getElementById("danger_level").value = d.danger_level_m;
                document.getElementById("reports").value = d.reports;
            });
        });
    }

    // Animate risk gauge
    var gauge = document.querySelector("[data-gauge]");
    if (gauge) {
        var target = gauge.dataset.gauge;
        gauge.style.width = "0%";
        setTimeout(function () { gauge.style.width = target + "%"; }, 100);
    }

    // Simple live search for tables: <input data-table-filter="#tableId">
    document.querySelectorAll("input[data-table-filter]").forEach(function (input) {
        input.addEventListener("input", function () {
            var rows = document.querySelectorAll(input.dataset.tableFilter + " tbody tr");
            var term = input.value.toLowerCase();
            rows.forEach(function (row) {
                row.style.display = row.textContent.toLowerCase().indexOf(term) > -1 ? "" : "none";
            });
        });
    });
});
