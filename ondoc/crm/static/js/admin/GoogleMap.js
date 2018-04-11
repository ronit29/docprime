function GoogleMap() {

  this.marker = null;
  this.requiredAccuracy = 50;
  this.init = function(){
    django.jQuery('#id_location_error').attr("readonly","readonly")
    var locText = django.jQuery('#id_location').val().replace("POINT (","").replace(")","").split(" ");
    
        var center = {lat: 0, lng: 0};
        if(locText.length>1)
            center = {lat: parseFloat(locText[1]), lng: parseFloat(locText[0])};

        
        this.map = new google.maps.Map(document.getElementById('gmap'), {
          zoom: 15,
          center: center
        });
        var error = parseFloat(django.jQuery('#id_location_error').val());

        this.addMarker(center, error)

     var self  =  this;
        django.jQuery('body').on('click','#get-loc',function(){
          django.jQuery('#loc-message').text("getting location ....");
          self.getCurrentLocation();
        });
    
        /*
        var marker = new google.maps.Marker({
          position: uluru,
          map: map
        });
        */
  }

  this.getCurrentLocation = function()
  {
    if(this.marker)
        this.marker.setMap(null);

    var self  =  this;
    if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(function(position) {

            self.renderMarker(position);
            
            console.log(position);

          }, function() {
            django.jQuery('#loc-message').text("could not get geolocation");          
          },{enableHighAccuracy:true,timeout:10000,maximumAge:0});
        } else {
          // Browser doesn't support Geolocation          
          django.jQuery('#loc-message').text("browser doesn't support geolocation");             
        }
  }

  this.renderMarker = function(position)
  {
      this.map.setCenter({lat: position.coords.latitude, lng: position.coords.longitude});
      var point = "POINT ("+position.coords.longitude+" "+position.coords.latitude+")";
      this.addMarker({lat: position.coords.latitude, lng: position.coords.longitude},position.coords.accuracy)

      if(position.coords.accuracy>this.requiredAccuracy)
      {
          django.jQuery('#loc-message').text("Location has "+position.coords.accuracy+" meters error. Try again");  
      
       }
       else
       {
            django.jQuery('#id_location').val(point);
            django.jQuery('#id_location_error').val(position.coords.accuracy);

            django.jQuery('#loc-message').text("Location Success");  
      }
  }
  this.addMarker = function(center, error)
  {
     this.circle = new google.maps.Circle({
            strokeColor: '#2974e5',
            strokeOpacity: 0.8,
            strokeWeight: 2,
            fillColor: '#2974e5',
            fillOpacity: 0.3,
            map: this.map,
            center: center,
            radius: error
          });

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