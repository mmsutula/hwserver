$(document).ready(function () 
{	
socket = new WebSocket("ws://xxx.xxx.xxx.xxx:8088/control.htm"); //swap in EMM IP address

socket.onmessage = function (event) 
		{
			$( "#main" ).append( "<p>"+event.data+"</p>" )
		};



socket.onopen = function (event)
{
var msg = {};
msg['task'] = ["wavelength_tune_start"];
msg['wavelength_2'] = 630;
msg['wavelength_step_2'] = 1;
msg['message_type'] = "page_update";
var msg2 = '{"wavelength_2":614,"wavelength_step_2":1,"task":["wavelength_tune_start"],"message_type":"page_update"}';
socket.send(JSON.stringify(msg));
};
})