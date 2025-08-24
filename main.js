const schedules = new Array(6).fill(0).map((e, i) => i + 1)
const groups = new Array(4).fill(0).map((e, i) => String.fromCharCode(i + 65))



console.log(schedules, groups)
let permutations = []

/**
 *
 *@param {number} k
 * @param {any[]} array
 */
function permute(k, array) {
    if (k == 1) return permutations.push(array.slice())

    
    if (k % 2 == 0){
        for (let i = 0; i < k - 1; i++) {
        
        }
    } else {
        for (let i = 0; i < k - 1; i++) {

        }
    }

}