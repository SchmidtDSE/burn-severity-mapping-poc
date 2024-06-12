function get200Json(response) {
  if (response.status == 200) {
    return response.json();
  } else {
    return new Promise((resolve, reject) => {
      reject(response.status);
    });
  }
}