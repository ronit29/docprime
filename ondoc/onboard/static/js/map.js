function GoogleMap() {

  this.marker = null;

  this.init = function(){
   
    var locText = $('#id_location').val().replace("SRID=4326;POINT (","").replace(")","").split(" ");
    
        var center = {lat: 28.460462, lng: 77.074852};
        if(locText.length>1)
        {
            center = {lat: parseFloat(locText[1]), lng: parseFloat(locText[0])};
            this.map = new google.maps.Map(document.getElementById('gmap'), {
              zoom: 15,
              center: center
            });
            
            this.addMarker(center);
        }
  }

  this.addMarker = function(center)
  {
       this.marker = new google.maps.Marker({
        position: center,
        map: this.map,
        title: 'location'
      });
   }
}

function initGoogleMap()
{
  setTimeout(function(){
    var map = new GoogleMap();
    map.init();
  },2000);
}